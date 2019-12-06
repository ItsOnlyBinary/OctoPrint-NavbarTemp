# coding=utf-8
from __future__ import absolute_import

__author__ = "Jarek Szczepanski <imrahil@imrahil.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 Jarek Szczepanski - Released under terms of the AGPLv3 License"

import octoprint.plugin
from octoprint.util import RepeatedTimer
import sys
import re
import os

from .libs.sbc import SBCFactory


class NavBarPlugin(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.piSocTypes = (["BCM2708", "BCM2709",
                            "BCM2835"])  # Array of raspberry pi SoC's to check against, saves having a large if/then statement later
        self.debugMode = False  # to simulate temp on Win/Mac
        self.displayTempSoC = True
        self.displayTempGPIO = True
        self._checkTempTimer = None
        self.sbc = None

    def on_after_startup(self):
        self.displayTempSoC = self._settings.get(["displayTempSoC"])
        self.displayTempGPIO = self._settings.get(["displayTempGPIO"])
        self.piSocTypes = self._settings.get(["piSocTypes"])
        self._logger.debug("displayTempSoC: %s" % self.displayTempSoC)

        if sys.platform == "linux2":
            self.sbc = SBCFactory().factory(self._logger)

            if self.sbc.is_supported and (self.displayTempSoC or self.displayTempGPIO):
                self._logger.debug("Let's start RepeatedTimer!")
                self.startTimer(10.0)
        # debug mode doesn't work if the OS is linux on a regular pc
        try:
            self._logger.debug("is supported? - %s" % self.sbc.is_supported)
        except:
            self._logger.debug("Embeded platform is not detected")


    def startTimer(self, interval):
        self._checkTempTimer = RepeatedTimer(interval, self.updateTemps, None, None, True)
        self._checkTempTimer.start()

    def updateTemps(self):
        gpio = 0
        soc = 0

        if self.displayTempGPIO:
            gpio = self.getTempGPIO()
        if self.displayTempSoC:
            soc = self.sbc.checkSoCTemp()

        self._logger.debug("soc: %s" % soc)
        self._plugin_manager.send_plugin_message(self._identifier,
                                                 dict(isSupported=self.sbc.is_supported,showsoc=self.displayTempSoC,
                                                      soctemp=soc,showgpio=self.displayTempGPIO,gpiotemp=gpio))

    def getTempGPIO(self):
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        base_dir = '/sys/bus/w1/devices/'
        device_folder = glob.glob(base_dir + '28*')[0]
        device_file = device_folder + '/w1_slave'
        if os.path.isfile(device_file):
            lines = self.readTempGPIO(device_file)
            count = 5
            while lines[0].strip()[-3:] != 'YES' and count <= 0:
                count -= 1
                time.sleep(0.1)
                lines = self.readTempGPIO(device_file)
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                p = '{0:0.1f}'.format(temp_c)
                return p
        return 'err'

    def readTempGPIO(self, device_file):
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

    ##~~ SettingsPlugin
    def get_settings_defaults(self):
        return dict(displayTempSoC=self.displayTempSoC,
                    piSocTypes=self.piSocTypes)

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        self.displayTempSoC = self._settings.get(["displayTempSoC"])

        if self.displayTempSoC:
            interval = 5.0 if self.debugMode else 30.0
            self.startTimer(interval)
        else:
            if self._checkTempTimer is not None:
                try:
                    self._checkTempTimer.cancel()
                except:
                    pass
            self._plugin_manager.send_plugin_message(self._identifier, dict())

    ##~~ TemplatePlugin API
    def get_template_configs(self):
        try:
            if self.sbc.is_supported:
                return [
                    dict(type="settings", template="navbartemp_settings_raspi.jinja2")
                ]
            else:
                return []
        except:
            return []

    ##~~ AssetPlugin API
    def get_assets(self):
        return {
            "js": ["js/navbartemp.js"],
            "css": ["css/navbartemp.css"],
            "less": ["less/navbartemp.less"]
        }

    ##~~ Softwareupdate hook
    def get_update_information(self):
        return dict(

            navbartemp=dict(
                displayName="Navbar Temperature Plugin",
                displayVersion=self._plugin_version,
                # version check: github repository
                type="github_release",
                user="imrahil",
                repo="OctoPrint-NavbarTemp",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/imrahil/OctoPrint-NavbarTemp/archive/{target_version}.zip"
            )
        )


__plugin_name__ = "Navbar Temperature Plugin"
__plugin_author__ = "Jarek Szczepanski"
__plugin_url__ = "https://github.com/imrahil/OctoPrint-NavbarTemp"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = NavBarPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }