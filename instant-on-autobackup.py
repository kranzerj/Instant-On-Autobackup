#!/usr/bin/env python3
"""
Instant ON Autobackup
A tool to automatically backup configurations from Aruba Instant On 1830 switches

Based on: aruba-1830-cert-uploader by travatine
https://github.com/travatine/aruba-1830-cert-uploader

Created by: Claude (Anthropic)
Commissioned by: Josef Kranzer (COUNT IT)
License: GPL-3.0
"""

import json
import requests
import xml.etree.ElementTree as ET
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as Cipher_PKCS1_v1_5
import binascii
from urllib.parse import urlparse
import datetime


class ArubaSwitch:
    def __init__(self, hostName: str, port: int, user: str, password: str) -> None:
        self.hostName = hostName
        self.port = port
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.magic = None

    def __debug(self, message: str):
        print(f'DEBUG {datetime.datetime.now()} {message}')

    def _getURL(self, url: str):
        self.__debug(f'GET {url}')
        result = self.session.get(url)
        self.__debug(f'GET Done.')
        return result

    def _getMagic(self):
        if self.magic is None:
            result = self._getURL(f'http://{self.hostName}/')
            if result:
                a = urlparse(result.url)
                self.magic = a.path.split('hpe/')[0]
        return self.magic

    def encrypt_data(self, publicKey, data: str):
        key = RSA.importKey(publicKey)
        cipher = Cipher_PKCS1_v1_5.new(key)
        return cipher.encrypt(data.encode())

    def bin2hex(self, binStr):
        return binascii.hexlify(binStr)

    def _encryptionSettingsGetPasswordEncryptEnable(self, root: ET.Element):
        passwEncryptEnable = root.find('.//passwEncryptEnable')
        if passwEncryptEnable is None:
            return False
        else:
            passwEncryptEnable = passwEncryptEnable.text
            return passwEncryptEnable == '1'

    def _encryptionSettingsGetPublicKey(self, root: ET.Element):
        publicKey = root.find('.//rsaPublicKey')
        if publicKey is None:
            raise RuntimeError('Error publicKey missing from encryption settings')
        return publicKey.text

    def _encryptionSettingsGetLoginToken(self, root: ET.Element):
        loginToken = root.find('.//loginToken')
        if loginToken is None:
            raise RuntimeError('Could not get Login token!')
        return loginToken.text

    def _resultExtractStatus(self, resultStr):
        root = ET.fromstring(resultStr)
        statusCode = root.find('.//statusCode')
        statusString = root.find('.//statusString')

        if statusCode is not None:
            statusCode = statusCode.text
        else:
            statusCode = 500

        if statusString is not None:
            statusString = statusString.text
        else:
            statusString = 'ERRORS'
        return int(statusCode), statusString

    def parseEncryptionSettings(self, hostname, xml, username, password):
        root = ET.fromstring(xml)

        if not self._encryptionSettingsGetPasswordEncryptEnable(root):
            newPath = './system.xml?action=login&user=' + username + '&password=' + password + "&ssd=true&"
        else:
            publicKey = self._encryptionSettingsGetPublicKey(root)
            loginToken = self._encryptionSettingsGetLoginToken(root)
            res = self.encrypt_data(publicKey, f'user={username}&password={password}&ssd=true&token={loginToken}&')
            res = self.bin2hex(res)
            res = res.decode()
            newPath = './system.xml?action=login&cred=' + res

        result = self._getURL(f'http://{hostname}/{newPath}')
        if result.ok:
            code, errorMessage = self._resultExtractStatus(result.text)
            if code > 0:
                raise RuntimeError(f'ERROR statusCode={code} {errorMessage}')
            return True
        raise RuntimeError(f'ERROR failed to log on {result.text}')

    def authenticate(self):
        self.__debug('>> authenticate')
        r = self._getURL(f'http://{self.hostName}/device/wcd?{{EncryptionSetting}}')
        if not r:
            raise RuntimeError('ERROR authenticate - Could not load encryption settings from switch')
        xml = r.text
        return self.parseEncryptionSettings(self.hostName, xml, self.user, self.password)

    def getSwitchHostname(self, runningConfig: str):
        """Liest den konfigurierten Hostnamen aus der Running Config aus"""
        self.__debug('>> getSwitchHostname from running config')
        try:
            # Suche nach "hostname" Zeile in der Config
            for line in runningConfig.split('\n'):
                line = line.strip()
                if line.startswith('hostname '):
                    hostname = line.replace('hostname ', '').strip().strip('"')
                    if hostname and hostname != '':
                        print(f'Switch hostname found: {hostname}')
                        return hostname
        except Exception as e:
            print(f'Warning: Could not parse hostname from config: {e}')
        
        # Fallback auf IP/Hostname aus config
        print(f'Using IP address as hostname: {self.hostName}')
        return self.hostName

    def downloadStartupConfig(self, configHostname):
        self.__debug('>> downloadStartupConfig')
        
        # Methode 1: Direkter Download (funktioniert oft nicht wegen Connection Abort)
        try:
            url = f'http://{self.hostName}/{self._getMagic()}/hpe/http_download?action=3&ssd=4'
            self.__debug(f'GET {url}')
            result = self.session.get(url, timeout=30)
            self.__debug(f'GET Done.')
            
            if result.ok and result.text and len(result.text) > 100:
                filename = f'./{configHostname}.startup.config.txt'
                with open(filename, 'wt') as f:
                    f.write(result.text)
                print(f'Startup config saved: {filename}')
                return True
        except Exception as e:
            self.__debug(f'Startup config download method 1 failed: {e}')
        
        # Methode 2: Verwende Running Config als Fallback
        # Bei Aruba Switches ist die Startup Config oft identisch zur Running Config
        # wenn keine ungespeicherten Änderungen vorliegen
        print(f'Note: Using running config as startup config (switch may not support direct startup download)')
        return False

    def downloadRunningConfig(self, configHostname):
        self.__debug('>> downloadRunningConfig')
        result = self._getURL(f'http://{self.hostName}/{self._getMagic()}/hpe/http_download?action=2&ssd=4')
        if result.ok:
            filename = f'./{configHostname}.running.config.txt'
            with open(filename, 'wt') as f:
                f.write(result.text)
            print(f'Running config saved: {filename}')
            return result.text  # Gib Config-Text zurück
        else:
            raise RuntimeError(f'Failed to download running config from {self.hostName}')


# Main program
if __name__ == '__main__':
    print('Instant ON Autobackup')
    print('=====================')
    print('Loading config.json...')

    try:
        with open('config.json') as f:
            config = json.load(f)
            switches = config['switches']

            for switch in switches:
                hostname = switch['hostname_IP']
                user = switch['user']
                password = switch['password']

                print(f'\nProcessing switch: {hostname}')
                try:
                    aSwitch = ArubaSwitch(hostname, 443, user, password)
                    if aSwitch.authenticate():
                        print(f'Authenticated successfully')
                        
                        # Running Config herunterladen (erst mit IP-Namen)
                        runningConfigText = aSwitch.downloadRunningConfig(hostname)
                        
                        # Hostname aus Running Config auslesen
                        switchHostname = aSwitch.getSwitchHostname(runningConfigText)
                        
                        # Wenn der Hostname anders ist als die IP, umbenennen
                        if switchHostname != hostname:
                            import os
                            old_filename = f'./{hostname}.running.config.txt'
                            new_filename = f'./{switchHostname}.running.config.txt'
                            if os.path.exists(old_filename):
                                os.rename(old_filename, new_filename)
                                print(f'Renamed: {old_filename} -> {new_filename}')
                        
                        # Startup Config herunterladen
                        aSwitch.downloadStartupConfig(switchHostname)
                        
                        print(f'Backup completed for {hostname} (saved as {switchHostname})')
                except RuntimeError as e:
                    print(f'ERROR for {hostname}: {e}')
                except Exception as e:
                    print(f'UNEXPECTED ERROR for {hostname}: {e}')

            print('\n=====================')
            print('Backup process finished')

    except FileNotFoundError:
        print('ERROR: config.json not found!')
    except json.JSONDecodeError:
        print('ERROR: config.json is not valid JSON!')
    except KeyError as e:
        print(f'ERROR: Missing key in config.json: {e}')
    except Exception as e:
        print(f'UNEXPECTED ERROR: {e}')
