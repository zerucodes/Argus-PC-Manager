#include <Windows.h>
#include <PhysicalMonitorEnumerationAPI.h>
#include <iostream>
#include <vector>
#include <string>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <map>
#include <HighLevelMonitorConfigurationAPI.h>
#include <LowLevelMonitorConfigurationAPI.h>
#include <unordered_map>
#pragma comment(lib, "Dxva2.lib")

struct CommandLineOptions {
    bool getMonitors = false;
    bool setVCP = false;
    bool getVCP = false;
    BYTE vcpCode = 0x0;
    DWORD value = 0;
    int monitorIndex = -1;
    std::string monitorName;
};

bool ParseCommandLine(int argc, char* argv[], CommandLineOptions& options);
bool GetPhysicalMonitorsInfo(HMONITOR hMonitor, std::vector<PHYSICAL_MONITOR>& physicalMonitors, int& deviceIndex);
bool WriteVCPCode(HANDLE hPhysicalMonitor, BYTE vcpCode, DWORD newValue);
bool ReadVCPCode(HANDLE hPhysicalMonitor, BYTE vcpCode, DWORD& currentValue, DWORD& maxValue);
std::unordered_map<std::string, std::string> GetMonitorCapabilities(HANDLE hMonitor);

BOOL CALLBACK MonitorEnumProc(HMONITOR hMonitor, HDC hdcMonitor, LPRECT lprcMonitor, LPARAM dwData) {
    auto physicalMonitors = reinterpret_cast<std::vector<PHYSICAL_MONITOR>*>(dwData);
    int deviceIndex = static_cast<int>(physicalMonitors->size());

    if (!GetPhysicalMonitorsInfo(hMonitor, *physicalMonitors, deviceIndex)) {
        std::cerr << "Failed to retrieve physical monitor information." << std::endl;
        return FALSE;
    }
    return TRUE;
}

std::wstring GetMonitorName(HMONITOR hMonitor) {
    MONITORINFOEX monitorInfo;
    monitorInfo.cbSize = sizeof(MONITORINFOEX);
    if (GetMonitorInfo(hMonitor, &monitorInfo)) {
        DISPLAY_DEVICE displayDevice;
        displayDevice.cb = sizeof(DISPLAY_DEVICE);
        if (EnumDisplayDevices(monitorInfo.szDevice, 0, &displayDevice, 0)) {
            return displayDevice.DeviceString;
        }
    }
    return L"Unknown";
}

int main(int argc, char* argv[]) {
    CommandLineOptions options;
    if (!ParseCommandLine(argc, argv, options)) {
        std::cerr << "Invalid command line parameters." << std::endl;
        return -1;
    }

    std::vector<PHYSICAL_MONITOR> physicalMonitors;
    if (!EnumDisplayMonitors(nullptr, nullptr, MonitorEnumProc, reinterpret_cast<LPARAM>(&physicalMonitors))) {
        std::cerr << "Failed to enumerate monitors." << std::endl;
        return -1;
    }

    if (options.getMonitors) {
        std::wcout << "{\"monitors\":[" ;
        for (size_t i = 0; i < physicalMonitors.size(); ++i) {
            //std::wcout << L"{'Monitors':[ " << i << L", Name: " << physicalMonitors[i].szPhysicalMonitorDescription << std::endl;
            auto capabilities = GetMonitorCapabilities(physicalMonitors[i].hPhysicalMonitor);
            //for (auto it = capabilities.begin(); it != capabilities.end(); ++it) {
            //    std::cout << it->first << " " << it->second << std::endl;
            //}

            std::cout << "{\"model\":\"" << capabilities["model"] << "\"" << ",\"name\":\"";
            std::wcout << physicalMonitors[i].szPhysicalMonitorDescription << "\"}";
            //std::wcout << "\"" << physicalMonitors[i].szPhysicalMonitorDescription << "\"";
            if (i != physicalMonitors.size() - 1) {
                std::wcout << ", ";
            }
        }
        std::wcout << "]}";
    }
    else if (options.getVCP || options.setVCP) {
        PHYSICAL_MONITOR zMonitor = { 0 };

        if (options.monitorIndex != -1 && options.monitorIndex < static_cast<int>(physicalMonitors.size())) {
            zMonitor = physicalMonitors[options.monitorIndex];
        }
        else {
            std::wstring wMonitorName(options.monitorName.begin(), options.monitorName.end());
            for (const auto& monitor : physicalMonitors) {
                std::wstring monitorDescription(monitor.szPhysicalMonitorDescription);
                if (monitorDescription.find(wMonitorName) != std::wstring::npos) {
                    zMonitor = monitor;
                    break;
                }
            }
        }
        DWORD newValue, maxValue;

        if (options.setVCP) {
            if (WriteVCPCode(zMonitor.hPhysicalMonitor, options.vcpCode, options.value)) {
                //std::cout << "VCP code " << (int)options.vcpCode << " from " << newValue << " set to " << options.value << " (max " << maxValue << ")" << std::endl;
            }
            else {
                std::cerr << "Failed to set VCP code." << std::endl;
            }
        }
        std::wstring monitorName(zMonitor.szPhysicalMonitorDescription);
        ReadVCPCode(zMonitor.hPhysicalMonitor, options.vcpCode, newValue, maxValue);

        std::wcout << "{\"response\":{\"monitor\":\"" << monitorName << "\",\"vcp\":" << int(options.vcpCode) << ",\"value\":" << newValue << ",\"max\":" << maxValue << "}}";
    }

    for (const auto& monitor : physicalMonitors) {
        DestroyPhysicalMonitor(monitor.hPhysicalMonitor);
    }

    return 0;
}

BYTE parseValue(const std::string& value) {
    int base = 10;
    if (value.substr(0, 2) == "0x") {
        base = 16;
    }
    int intValue = std::stoi(value, nullptr, base);
    if (intValue < 0 || intValue > 255) {
        throw std::out_of_range("Value out of range for BYTE");
    }
    return static_cast<BYTE>(intValue);
}

bool ParseCommandLine(int argc, char* argv[], CommandLineOptions& options) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-getMonitors") {
            options.getMonitors = true;
        }
        else if (arg == "-getVCP") {
            options.getVCP = true;
        }
        else if (arg == "-setVCP") {
            options.setVCP = true;
        }
        else if (arg.find("--vcp=") == 0) {
            options.vcpCode = parseValue(arg.substr(6));
        }
        else if (arg.find("--value=") == 0) {
            options.value = std::stoi(arg.substr(8));
        }
        else if (arg.find("--monitor=") == 0) {
            std::string monitorParam = arg.substr(10);
            try {
                options.monitorIndex = std::stoi(monitorParam);
            }
            catch (...) {
                options.monitorName = monitorParam;
            }
        }
        else {
            return false;
        }
    }
    return true;
}

bool GetPhysicalMonitorsInfo(HMONITOR hMonitor, std::vector<PHYSICAL_MONITOR>& physicalMonitors, int& deviceIndex) {
    DWORD numPhysicalMonitors = 0;
    if (!GetNumberOfPhysicalMonitorsFromHMONITOR(hMonitor, &numPhysicalMonitors)) {
        std::cerr << "Failed to get the number of physical monitors." << std::endl;
        return false;
    }

    std::vector<PHYSICAL_MONITOR> monitors(numPhysicalMonitors);
    if (!GetPhysicalMonitorsFromHMONITOR(hMonitor, numPhysicalMonitors, monitors.data())) {
        std::cerr << "Failed to get physical monitors." << std::endl;
        return false;
    }

    physicalMonitors.insert(physicalMonitors.end(), monitors.begin(), monitors.end());
    return true;
}

std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(' ');
    if (first == std::string::npos)
        return str;
    size_t last = str.find_last_not_of(' ');
    return str.substr(first, (last - first + 1));
}

// Function to parse key-value pairs from the capabilities string
std::unordered_map<std::string, std::string> parseCapabilities(const std::string& capabilitiesString) {
    std::unordered_map<std::string, std::string> capabilities;
    std::istringstream stream(capabilitiesString);
    std::string token;

    while (std::getline(stream, token, ')')) {
        size_t start = token.find('(');
        if (start != std::string::npos) {
            std::string key = trim(token.substr(0, start));
            std::string value = trim(token.substr(start + 1));
            capabilities[key] = value;
        }
    }

    return capabilities;
}

std::unordered_map<std::string, std::string> GetMonitorCapabilities(HANDLE hMonitor) {
    // Get the size of the capabilities string
    DWORD capabilitiesStringLength = 0;
    std::unordered_map<std::string, std::string> capabilities;
    if (!GetCapabilitiesStringLength(hMonitor, &capabilitiesStringLength)) {
        std::cerr << "Failed to get the size of the capabilities string. Error: " << GetLastError() << std::endl;
        return capabilities;
    }

    // Allocate buffer for the capabilities string
    char* capabilitiesString = new char[capabilitiesStringLength];

    // Call the function to get the capabilities string
    if (CapabilitiesRequestAndCapabilitiesReply(hMonitor, capabilitiesString, capabilitiesStringLength)) {
        capabilities = parseCapabilities(capabilitiesString);
    }
    else {
        std::cerr << "Failed to get monitor capabilities. Error: " << GetLastError() << std::endl;
    }
    
    //std::cout << "Model Name: " << capabilities["model"] << std::endl;
    // Clean up
    delete[] capabilitiesString;
    return capabilities;
}
bool ReadVCPCode(HANDLE hPhysicalMonitor, BYTE vcpCode, DWORD& currentValue, DWORD& maxValue) {
    MC_VCP_CODE_TYPE type;
    DWORD current, maximum;
    if (GetVCPFeatureAndVCPFeatureReply(hPhysicalMonitor, vcpCode, &type, &current, &maximum)) {
        currentValue = current;
        maxValue = maximum;
        return true;
    }
    else {
        std::cerr << "Failed to get VCP code 0x" << std::hex << (int)vcpCode << std::dec << std::endl;
        return false;
    }
}

bool WriteVCPCode(HANDLE hPhysicalMonitor, BYTE vcpCode, DWORD newValue) {
    if (SetVCPFeature(hPhysicalMonitor, vcpCode, newValue)) {
        return true;
    }
    else {
        std::cerr << "Failed to set VCP code 0x" << std::hex << (int)vcpCode << std::dec << " to " << newValue << std::endl;
        return false;
    }
}