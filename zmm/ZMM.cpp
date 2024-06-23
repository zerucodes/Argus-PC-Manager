#include <Windows.h>
#include <PhysicalMonitorEnumerationAPI.h>
#include <iostream>
#include <vector>
#include <string>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <HighLevelMonitorConfigurationAPI.h>
#include <LowLevelMonitorConfigurationAPI.h>

#pragma comment(lib, "Dxva2.lib")

// Define the necessary structures and constants for VCP codes
#define IOCTL_VIDEO_QUERY_SUPPORTED_BRIGHTNESS    CTL_CODE(FILE_DEVICE_VIDEO, 0x126, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS      CTL_CODE(FILE_DEVICE_VIDEO, 0x127, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS        CTL_CODE(FILE_DEVICE_VIDEO, 0x128, METHOD_BUFFERED, FILE_ANY_ACCESS)

typedef struct _DISPLAY_BRIGHTNESS {
    UCHAR ucDisplayPolicy;
    UCHAR ucACBrightness;
    UCHAR ucDCBrightness;
} DISPLAY_BRIGHTNESS, * PDISPLAY_BRIGHTNESS;

struct CommandLineOptions {
    bool getMonitors = false;
    bool setVCP = false;
    int vcpCode = 0;
    DWORD value = 0;
    int monitorIndex = -1;
    std::string monitorName;
};

bool ParseCommandLine(int argc, char* argv[], CommandLineOptions& options);
bool GetPhysicalMonitorsInfo(HMONITOR hMonitor, std::vector<PHYSICAL_MONITOR>& physicalMonitors, int& deviceIndex);
bool ReadBrightness(HANDLE hPhysicalMonitor, DWORD& currentValue, DWORD& maxValue);
bool SetBrightness(HANDLE hPhysicalMonitor, DWORD newValue);
bool WriteVCPCode(HANDLE hPhysicalMonitor, BYTE vcpCode, DWORD newValue);

BOOL CALLBACK MonitorEnumProc(HMONITOR hMonitor, HDC hdcMonitor, LPRECT lprcMonitor, LPARAM dwData) {
    auto physicalMonitors = reinterpret_cast<std::vector<PHYSICAL_MONITOR>*>(dwData);
    int deviceIndex = static_cast<int>(physicalMonitors->size());
    // std::wcout << L"Monitor #" << deviceIndex << L", Monitor Name: ";

    if (!GetPhysicalMonitorsInfo(hMonitor, *physicalMonitors, deviceIndex)) {
        std::cerr << "Failed to retrieve physical monitor information." << std::endl;
        return FALSE;
    }

    // std::wcout << physicalMonitors->back().szPhysicalMonitorDescription << std::endl;
    return TRUE;
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
        for (size_t i = 0; i < physicalMonitors.size(); ++i) {
            std::wcout << L"Monitor #" << i << L", Name: " << physicalMonitors[i].szPhysicalMonitorDescription << std::endl;
        }
    }
    else if (options.setVCP) {
        HANDLE targetMonitor = nullptr;
        if (options.monitorIndex != -1 && options.monitorIndex < static_cast<int>(physicalMonitors.size())) {
            targetMonitor = physicalMonitors[options.monitorIndex].hPhysicalMonitor;
        }
        else {
            std::wstring wMonitorName(options.monitorName.begin(), options.monitorName.end());
            for (const auto& monitor : physicalMonitors) {
                std::wstring monitorDescription(monitor.szPhysicalMonitorDescription);

                if (monitorDescription.find(wMonitorName) != std::wstring::npos) {
                    targetMonitor = monitor.hPhysicalMonitor;
                    std::wcout << "Chaning Setting for " << monitorDescription << std::endl;
                    break;
                }
            }
        }
        if (WriteVCPCode(targetMonitor, static_cast<BYTE>(options.vcpCode), options.value)) {
            std::cout << "VCP code 0x" << options.vcpCode << " set to " << options.value << std::endl;
        }
        else {
            std::cerr << "Failed to set VCP code." << std::endl;
        }
    }

    for (const auto& monitor : physicalMonitors) {
        DestroyPhysicalMonitor(monitor.hPhysicalMonitor);
    }

    return 0;
}

bool ParseCommandLine(int argc, char* argv[], CommandLineOptions& options) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-getMonitors") {
            options.getMonitors = true;
        }
        else if (arg == "-setVCP") {
            options.setVCP = true;
        }
        else if (arg.find("--vcp=") == 0) {
            options.vcpCode = std::stoi(arg.substr(6));
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

bool ReadBrightness(HANDLE hPhysicalMonitor, DWORD& currentValue, DWORD& maxValue) {
    DISPLAY_BRIGHTNESS brightness;
    DWORD bytesReturned;

    if (DeviceIoControl(hPhysicalMonitor, IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS, NULL, 0, &brightness, sizeof(brightness), &bytesReturned, NULL)) {
        currentValue = brightness.ucACBrightness;
        maxValue = 100; // Typically, brightness is represented as a percentage from 0 to 100
        return true;
    }
    else {
        std::cerr << "Failed to get brightness." << std::endl;
        return false;
    }
}

std::string intToHex(int value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::uppercase << value;
    return oss.str();
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