# Tracker for Ubiquiti Unifi Controller (Updated for UniFi OS / Cloud Gateways)

import Domoticz
import requests
import json
import urllib3
from trackers.tracker_base import tracker

# Potlačenie varovania o neplatnom SSL certifikáte
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class http_unifi(tracker):
    def __init__(self, *args, **kwargs):
        # 1. Najprv zavoláme super().__init__, aby sa vytvorili základné atribúty
        super().__init__(*args, **kwargs)

        # 2. Ttracker_port existuje (vytvoril ho super)
        # Ak v nastaveniach Domoticz nie je port vyplnený, nastavíme 443
        if (
            not hasattr(self, "tracker_port")
            or self.tracker_port is None
            or self.tracker_port == ""
        ):
            self.tracker_port = 443

        # 3. Zvyšok inicializácie
        self.baseurl = "https://{}:{}".format(self.tracker_ip, self.tracker_port)
        self.site = "default"
        self.verify_ssl = False
        self.is_unifi_os = False
        self.prepare_for_polling()

    def poll_present_tag_ids(self):
        try:
            if not self.http_session:
                if not self.connect():
                    return

            # Ak je to UniFi OS, prefix /proxy/network
            prefix = "/proxy/network" if self.is_unifi_os else ""
            url = "{}{}/api/s/{}/stat/sta".format(self.baseurl, prefix, self.site)

            response = self.http_session.get(url, verify=self.verify_ssl, timeout=10)

            if response.status_code == 401:
                Domoticz.Debug(self.tracker_ip + " Session expired, reconnecting...")
                self.close_connection()
                return

            raw_data = response.text
            Domoticz.Debug(self.tracker_ip + " Returned: " + raw_data)
            self.receiver_callback(raw_data)

        except Exception as e:
            Domoticz.Error(self.tracker_ip + " Polling error: " + str(e))
            self.close_connection()

    def connect(self):
        login_data = {
            "username": self.tracker_user,
            "password": self.tracker_password,
            "remember": True,
        }

        self.http_session = requests.Session()

        # najprv UniFi OS prihlásenie (/api/auth/login)
        login_url = "{}/api/auth/login".format(self.baseurl)
        try:
            response = self.http_session.post(
                login_url, json=login_data, verify=self.verify_ssl, timeout=10
            )

            if response.status_code == 200:
                self.is_unifi_os = True
                Domoticz.Status(
                    self.tracker_ip + " Connected to UniFi OS (Cloud Gateway)"
                )
                return True

            # 2. Ak 1. zlyhalo, starý spôsob (/api/login)
            login_url_old = "{}/api/login".format(self.baseurl)
            response = self.http_session.post(
                login_url_old, json=login_data, verify=self.verify_ssl, timeout=10
            )

            if response.status_code == 200:
                self.is_unifi_os = False
                Domoticz.Status(
                    self.tracker_ip + " Connected to Legacy UniFi Controller"
                )
                return True

            Domoticz.Error(
                self.tracker_ip
                + " Login failed (Status: {})".format(response.status_code)
            )
            return False

        except Exception as e:
            Domoticz.Error(
                self.tracker_ip + " Connection error during login: " + str(e)
            )
            return False

    def disconnect(self):
        try:
            logout_path = "/api/auth/logout" if self.is_unifi_os else "/logout"
            self.http_session.get(
                "{}{}".format(self.baseurl, logout_path), verify=self.verify_ssl
            )
        except:
            pass
        finally:
            self.close_connection()

    def close_connection(self):
        try:
            if self.http_session:
                self.http_session.close()
            self.http_session = None
            Domoticz.Debug(self.tracker_ip + " HTTP session closed")
        except Exception as e:
            Domoticz.Debug(self.tracker_ip + " Close session exception: " + str(e))

    def prepare_for_polling(self):
        if self.connect():
            self.is_ready = True

    def stop_now(self):
        self.is_ready = False
        self.disconnect()
        super().stop_now()
