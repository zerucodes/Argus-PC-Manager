import time
import threading
import argus
import sys
import os
import unittest
import socket
sys.path.append(os.getcwd)


class TestArgus(unittest.TestCase):
    def setUp(self):  # Sender 168, Reciever 169
        self.senderPort = 268  # Test port
        self.sender = argus.setup_sender_socket(self.senderPort)

    def test_connection(self):
        str = 'test_connection'
        time.sleep(0.2)
        argus_ip = argus.local_ip  # '192.168.1.121' remote argus
        result = self.sender.sendto(str.encode(), (argus_ip, 169))
        assertion = self.assertEqual(result, len(str))

        if assertion:
            print(assertion)

    def test_change_input(self):
        str = 'argus.monitor 2 input dp'  # Set 2nd monitor input to DisplayPort
        time.sleep(0.2)
        argus_ip = argus.local_ip  # '192.168.1.121' remote argus
        result = self.sender.sendto(str.encode(), (argus_ip, 169))
        assertion = self.assertEqual(result, len(str))
        if assertion:
            print(assertion)

    def test_change_input2(self):
        str = 'argus.monitor 1 input usbc'  # Set 1st monitor input to usbc
        time.sleep(0.2)
        argus_ip = argus.local_ip  # '192.168.1.121' remote argus
        result = self.sender.sendto(str.encode(), (argus_ip, 169))
        assertion = self.assertEqual(result, len(str))
        if assertion:
            print(assertion)

    def tearDown(self):
        print(f'Closing sender socket')
        self.sender.close()


if __name__ == '__main__':
    unittest.main()
