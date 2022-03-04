import datetime
import json

import dateutil.parser
import pytz
import requests

from gamest.errors import UnsupportedAppError
from gamest.plugins import GamestSessionPlugin, NotificationService


class RetroachievementsPlugin(GamestSessionPlugin):
    SETTINGS_TAB_NAME = "RetroAchievements"
    API_URL = 'https://retroachievements.org/API/'

    def __init__(self, application):
        super().__init__(application)
        self.job = None
        if self.play_session.user_app.identifier_plugin != 'RetroarchIdentifierPlugin':
            raise UnsupportedAppError("Current app not identified by RetroarchIdentifierPlugin.")

        try:
            self.latest_summary = (self.config.get('latest_summary', type=json.loads)
                                   or self.get_summary())
        except Exception:
            self.latest_summary = None

        application.bind("<<GameStart{}>>".format(self.play_session.id), self.onGameStart, "+")
        application.bind("<<GameEnd{}>>".format(self.play_session.id), self.onGameEnd, "+")

        self.logger.debug("Plugin initialized: %s", self.__class__)

    @classmethod
    def get_settings_template(cls):
        d = super().get_settings_template()

        d[(cls.__name__, 'user')] = {
            'name': 'User name',
            'type': 'text',
            'default': '',
            'hint': ("Your RetroAchievements user name"),
        }

        d[(cls.__name__, 'api_key')] = {
            'name': 'API key',
            'type': 'text',
            'default': '',
            'hint': ("Your RetroAchievements Web API key"),
        }

        d[(cls.__name__, 'add_status_updates')] = {
            'name': 'Save updates in DB',
            'type': 'bool',
            'default': True,
            'hint': "If checked, status updates from this plugin will be saved to the database.",
        }

        d[(cls.__name__, 'notify')] = {
            'name': 'Notify on updates',
            'type': 'bool',
            'default': True,
            'hint': "If checked, status updates from this plugin will be sent to e.g. Discord.",
        }

        d[(cls.__name__, 'interval')] = {
            'name': 'Update interval (minutes)',
            'type': 'text',
            'validate': int,
            'default': '5',
            'hint': "How often to send updates, in minutes.",
        }

        return d

    @property
    def api_key(self):
        return self.config.get('api_key')

    @property
    def user(self):
        return self.config.get('user')

    @property
    def add_status_updates(self):
        return self.config.getboolean('add_status_updates', fallback=True)

    @property
    def notify(self):
        return self.config.getboolean('notify', fallback=True)

    @property
    def interval(self):
        return self.config.get('interval', type=int, fallback=5)

    def onGameStart(self, e):
        self.logger.debug("onGameStart called")
        self.job = self.application.after(5*60*1000, self.report_update)

    def onGameEnd(self, e):
        self.logger.debug("onGameEnd called")
        self.report_update(game_end=True)
        self.cleanup()

    def cleanup(self):
        if self.job:
            self.application.after_cancel(self.job)

    @classmethod
    def api_url(cls, endpoint):
        """Return the full URL for an API endpoint."""
        return cls.API_URL + endpoint

    def query_params(self, **params):
        """Return a dict containing the auth info plus the given params."""
        return dict(z=self.user, y=self.api_key, **params)

    def get_api_response(self, endpoint, **params):
        """Return the API response on the given endpoint."""
        r = requests.get(self.api_url(endpoint), params=self.query_params(**params))
        return r.json()

    def get_summary(self):
        try:
            r = self.get_api_response('API_GetUserSummary.php', u=self.user, g=5)
        except Exception:
            return None
        if r['Status'] == 'Offline':
            return None
        summary = {
            'presence': r['RichPresenceMsg'],
            'achievements': r['RecentAchievements'].get(r['LastGameID']),
        }
        self.config.set('latest_summary', json.dumps(summary))
        return summary

    def get_report(self):
        if not (self.user and self.api_key):
            return None
        summary = self.get_summary()
        if not summary:
            return None
        if summary == self.latest_summary:
            self.logger.debug("No change found in latest_summary.")
            return None
        else:
            if self.latest_summary is None:
                self.latest_summary = summary
            report = summary['presence']
            new_achievements = []
            for k, v in summary['achievements'].items():
                ago = datetime.datetime.now(pytz.utc) - dateutil.parser.parse(v['DateAwarded']+'Z')
                if (k not in self.latest_summary['achievements'] and
                        ago < datetime.timedelta(seconds=2*self.interval*60)):
                    new_achievements.append('**{}**: {} ({} points)'.format(
                        v['Title'], v['Description'], v['Points']))
            if new_achievements:
                report += '\n\n{} new achievements:\n\n'.format(len(new_achievements))
                report += '\n\n'.join(new_achievements)

            self.latest_summary = summary
            return report

    def report_update(self, game_end=False):
        self.logger.debug("report_update called")
        if game_end:
            report_text = "{{user_name}} played **{}**:\n\n".format(
                self.play_session.user_app.app)
        else:
            report_text = "{{user_name}} is playing **{}**:\n\n".format(
                self.play_session.user_app.app)
        try:
            report_details = self.get_report()
            if report_details:
                if self.add_status_updates:
                    self.play_session.add_status_update(report_details)
                report_text = report_text + report_details
                if self.notify:
                    for s in filter(lambda p: isinstance(p, NotificationService),
                                    self.application.persistent_plugins):
                        s.notify(report_text)
            else:
                self.logger.debug("No difference since report.")
        except Exception:
            self.logger.exception("Failed to build update.")
        finally:
            if self.application.RUNNING and self.play_session is self.application.play_session:
                self.job = self.application.after(self.interval*60*1000, self.report_update)
