import os
import logging
import json
import urllib

import sh
import sqlalchemy.exc
from sqlalchemy import create_engine
from alembic import command
from alembic.migration import MigrationContext
from alembic.config import Config
from alembic.script import ScriptDirectory
from flask import current_app

from alarmdecoder.util.firmware import Firmware

from .constants import FIRMWARE_JSON_URL

try:
    current_app._get_current_object()
    running_in_context = True
except RuntimeError:
    running_in_context = False

def _print(*args, **kwargs):
    fmt, arguments = args[0], args[1:]
    print(fmt.format(*arguments))

def _log(*args, **kwargs):
    logLevel = kwargs.pop('logLevel', logging.INFO)

    if running_in_context:
        current_app.logger.log(logLevel, *args, **kwargs)
    else:
        _print(*args, **kwargs)


class Updater(object):
    """
    The primary update system
    """
    def __init__(self):
        """
        Constructor
        """
        self._components = {}

        self._components['AlarmDecoderWebapp'] = WebappUpdater('AlarmDecoderWebapp', project_url='https://github.com/nutechsoftware/alarmdecoder-webapp')
        self._components['AlarmDecoderLibrary'] = SourceUpdater('AlarmDecoderLibrary', project_url='https://github.com/nutechsoftware/alarmdecoder', path=current_app.config['ALARMDECODER_LIBRARY_PATH'])
        # TODO: ser2sock goes here, if installed from source.

    def check_updates(self):
        """
        Performs a check for component updates

        :returns: A list of components and their statuses.
        """
        status = {}

        for name, component in self._components.iteritems():
            component.refresh()
            status[name] = (component.needs_update, component.branch, component.local_revision, component.remote_revision, component.status, component.project_url)

        return status

    def check_firmware(self):

        version = None
        if current_app.decoder.device:
            version = current_app.decoder.device.version_number

        ret = False

        if version is not None and version != '':
            data = None
            version = version[1:]
            try:
                response = urllib.urlopen(FIRMWARE_JSON_URL)
                data = json.loads(response.read())
                for firmware in data['firmware']:
                    if firmware['tag'] == "Stable":
                        if version != firmware['version']:
                            ret = True
                        else:
                            ret = False
                            break

            except IOError:
                ret = False

        return ret

    def update(self, component_name=None):
        """
        Updates the specificed component or all components.

        :param component_name: Name of the component to update.
        :type component_name: string

        :returns: A list of components and the status after the update.
        """
        ret = {}

        _log('Starting update process..')

        if component_name is not None:
            component = self._components[component_name]

            ret[component_name] = component.update()
        else:
            for name, component in self._components.iteritems():
                if component.needs_update():
                    ret[component_name] = component.update()

        _log('Update process finished.')

        return ret


class WebappUpdater(object):
    """
    Update system for the webapp.  Encapsulates source and database for this product.
    """

    def __init__(self, name, project_url=None):
        """
        Constructor

        :param name: Name of the component
        :type name: string
        """

        self.name = name
        self.project_url = project_url
        #self._enabled, self._status = self._check_enabled()
        self._enabled = True

        self._source_updater = SourceUpdater('AlarmDecoderWebapp', project_url=project_url, path=None)
        self._db_updater = DBUpdater()

    @property
    def branch(self):
        """Returns the current branch"""
        return self._source_updater.branch

    @property
    def local_revision(self):
        """Returns the current local revision"""
        return self._source_updater.local_revision

    @property
    def remote_revision(self):
        """Returns the current remote revision"""
        return self._source_updater.remote_revision

    @property
    def commit_count(self):
        """Returns the number of commits behind and ahead of the remote branch"""
        return self._source_updater.commits_behind, self._source_updater.commits_ahead

    @property
    def status(self):
        """Returns the status string"""
        return self._source_updater.status

    @property
    def needs_update(self):
        """Determines if a component needs an update"""
        if self._enabled:
            behind, ahead = self._source_updater.commit_count

            if behind is not None and behind > 0:
                return True

        return False

    @property
    def version(self):
        version = ''

        try:
            version = sh.git('describe', tags=True, always=True, long=True)
        except:
            pass

        return version.strip()

    def refresh(self):
        """
        Refreshes the component status
        """

        if not self._enabled:
            return

        self._source_updater.refresh()
        self._db_updater.refresh()

    def update(self):
        """
        Performs the update

        :returns: Returns the update results
        """
        _log('WebappUpdater: starting..')

        ret = { 'status': 'FAIL', 'restart_required': False }

        if not self._enabled:
            _log('WebappUpdater: disabled')
            return ret

        git_succeeded = False
        db_succeeded = False
        git_revision = self._source_updater.local_revision
        db_revision = self._db_updater.current_revision

        try:
            git_succeeded = self._source_updater.update()

            if git_succeeded:
                self._db_updater.refresh()
                db_succeeded = self._db_updater.update()

        except sh.ErrorReturnCode:
            git_succeeded = False

        if not git_succeeded or not db_succeeded:
            _log('WebappUpdater: failed - [{0},{1}]'.format(git_succeeded, db_succeeded), logLevel=logging.ERROR)

            if not db_succeeded:
                self._db_updater.downgrade(db_revision)

            if not git_succeeded or not db_succeeded:
                self._source_updater.reset(git_revision)

            return ret

        _log('WebappUpdater: success')

        ret['status'] = 'PASS'
        ret['restart_required'] = True

        return ret


class SourceUpdater(object):
    """
    Git-based update system
    """

    def __init__(self, name, project_url='', path=None):
        """
        Constructor

        :param name: Name of the component
        :type name: string
        """

        self._path = None
        try:
            if path is not None:
                self._git = sh.git.bake(work_tree=path, git_dir=os.path.join(path, '.git'))
                self._path = path
            else:
                self._git = sh.git

        except sh.CommandNotFound:
            self._git = None

        self.name = name
        self.project_url = project_url
        self._branch = ''
        self._local_revision = None
        self._remote_revision = None
        self._commits_ahead = 0
        self._commits_behind = 0
        self._enabled, self._status = self._check_enabled()

    @property
    def branch(self):
        """Returns the current branch"""
        return self._branch

    @property
    def local_revision(self):
        """Returns the current local revision"""
        return self._local_revision

    @property
    def remote_revision(self):
        """Returns the current remote revision"""
        return self._remote_revision

    @property
    def commit_count(self):
        """Returns the number of commits behind and ahead of the remote branch"""
        return self._commits_behind, self._commits_ahead

    @property
    def status(self):
        """Returns the status string"""
        return self._status

    @property
    def needs_update(self):
        """Determines if a component needs an update"""
        if self._enabled:
            behind, ahead = self.commit_count

            if behind is not None and behind > 0:
                return True

        return False

    def refresh(self):
        """
        Refreshes the component status
        """
        self._update_status()

        if not self._enabled:
            return

        self._fetch()

        self._retrieve_branch()
        self._retrieve_local_revision()
        self._retrieve_remote_revision()
        self._retrieve_commit_count()

    def update(self):
        """
        Performs the update

        :returns: Returns the update results
        """
        _log('SourceUpdater: starting..')

        ret = {}

        if not self._enabled:
            _log('SourceUpdater: disabled')
            return False

        git_succeeded = False
        git_revision = self.local_revision

        try:
            self._git.merge('origin/{0}'.format(self.branch))
            git_succeeded = True

        except sh.ErrorReturnCode:
            git_succeeded = False

        if not git_succeeded:
            _log('SourceUpdater: failed.', logLevel=logging.ERROR)

            return False

        _log('SourceUpdater: success')

        ret['status'] = 'PASS'
        ret['restart_required'] = True

        return ret

    def reset(self, revision):
        try:
            self._git('reset', '--hard', revision)
        except sh.ErrorReturnCode:
            # TODO do something here?
            pass

    def _retrieve_commit_count(self):
        """
        Retrieves the commit counts
        """
        try:
            results = self._git('rev-list', '@{upstream}...HEAD', left_right=True).strip()

            self._commits_behind, self._commits_ahead = results.count('<'), results.count('>')
            self._update_status()
        except sh.ErrorReturnCode:
            self._commits_behind, self._commits_ahead = 0, 0

    def _retrieve_branch(self):
        """
        Retrieves the current branch
        """
        try:
            results = self._git('symbolic-ref', 'HEAD', q=True).strip()
            self._branch = results.replace('refs/heads/', '')
        except sh.ErrorReturnCode:
            self._branch = ''

    def _retrieve_local_revision(self):
        """
        Retrieves the current local revision
        """
        try:
            self._local_revision = self._git('rev-parse', 'HEAD').strip()
        except sh.ErrorReturnCode:
            self._local_revision = None

    def _retrieve_remote_revision(self):
        """
        Retrieves the current remote revision
        """
        results = None

        try:
            results = self._git('rev-parse', '--verify', '--quiet', '@{upstream}').strip()

            if results == '':
                results = None
        except sh.ErrorReturnCode:
            pass

        self._remote_revision = results

    def _fetch(self):
        """
        Performs a fetch from the origin
        """
        try:
            # HACK:
            #
            # Ran into an issue when trying to fetch from an ssh-based
            # repository and need a good way to make sure that fetch doesn't
            # forever block while asking for an ssh password.  _bg didn't do
            # the job but a combination of _iter and _timeout seems to work
            # fine.
            #
            for c in self._git.fetch('origin', _iter_noblock=True, _timeout=30):
                pass
        except sh.TimeoutException:
            pass
        except sh.ErrorReturnCode:
            pass

    def _update_status(self, status=''):
        """
        Updates the status string
        """
        self._status = status

        enabled, enabled_status = self._check_enabled()

        if not enabled:
            self._status = enabled_status
        else:
            temp_status = []
            if self._commits_behind is not None and self._commits_behind > 0:
                temp_status.append('{0} commit{1} behind'.format(self._commits_behind, '' if self._commits_behind == 1 else 's'))

            if self._commits_ahead is not None and self._commits_ahead > 0:
                temp_status.append('{0} commit{1} ahead'.format(self._commits_ahead, '' if self._commits_ahead == 1 else 's'))

            if len(temp_status) == 0:
                self._status = 'Up to date!'
            else:
                self._status += ', '.join(temp_status)

    def _check_enabled(self):
        """
        Determine if this update component is enabled

        :returns: Whether or not this component is enabled.
        """
        git_available = self._git is not None

        path_exists = False
        if self._path is not None:
            path_exists = os.path.exists(self._path)

        remote_okay = self._check_remotes()

        status = ''
        if not git_available:
            status = 'Disabled (Git is unavailable)'
        elif self._path is not None and not path_exists:
            status = 'Disabled (unable to find path)'
        elif not remote_okay:
            status = 'Disabled (SSH origin)'

        return (git_available and remote_okay and (self._path is None or path_exists), status)

    def _check_remotes(self):
        """
        Hack of a check determine if our origin remote is via ssh since it
        blocks if the key has a password.

        :returns: Whether or not we're running with an ssh remote.
        """
        if not self._git:
            return True

        try:
            remotes = self._git.remote(v=True)
            for r in remotes.strip().split("\n"):
                name, path = r.split("\t")
                if name == 'origin' and '@' in path:
                    return False
        except sh.ErrorReturnCode_128:
            return False

        return True


class DBUpdater(object):
    """
    Database update system
    """

    def __init__(self):
        """
        Constructor
        """
        self._config = Config()
        self._config.set_main_option("script_location", "alembic")

        self._script = ScriptDirectory.from_config(self._config)
        self._engine = create_engine(current_app.config.get('SQLALCHEMY_DATABASE_URI'))

    @property
    def needs_update(self):
        """Returns whether or not the component needs an update"""
        if self.current_revision != self.newest_revision:
            return True

        return False

    @property
    def current_revision(self):
        """Returns the current database revision"""
        return self._current_revision

    @property
    def newest_revision(self):
        """Returns the newest revision available"""
        return self._newest_revision

    @property
    def status(self):
        """Returns the component status"""
        return ''

    def refresh(self):
        """
        Refreshes the component status
        """
        self._open()

        self._current_revision = self._context.get_current_revision()
        self._newest_revision = self._script.get_current_head()

        self._close()

        return True

    def update(self):
        """
        Performs the update

        :returns: The update results
        """

        if self._current_revision != self._newest_revision:
            _log('DBUpdater: starting..')

            try:
                script_directory = ScriptDirectory.from_config(self._config)

                revision_list = []
                for script in script_directory.walk_revisions(self._current_revision, self._newest_revision):
                    if script.revision != self._current_revision:
                        revision_list.append(script.revision)

                for rev in reversed(revision_list):
                    try:
                        _log('Applying database revision: {0}'.format(rev))
                        command.upgrade(self._config, rev)
                    except sqlalchemy.exc.OperationalError as err:
                        if 'already exists' in str(err):
                            _log('Table already exists.. stamping to revision.')
                            self._stamp_database(rev)

            except sqlalchemy.exc.OperationalError as err:
                _log('DBUpdater: failure - {0}'.format(err), logLevel=logging.ERROR)

                return False

            _log('DBUpdater: success')

        return True

    def downgrade(self, rev):
        try:
            command.downgrade(self._config, rev)

        except sqlalchemy.exc.OperationalError as err:
            _log('DBUpdater: failed to downgrade release: {0}'.format(err), logLevel=logging.ERROR)
            raise err

    def _stamp_database(self, rev):
        try:
            command.stamp(self._config, rev)
        except sqlalchemy.exc.OperationalError as err:
            _log('DBUpdater: stamp database - failure - {0}'.format(err), logLevel=logging.ERROR)
            raise err

    def _open(self):
        """
        Create a connection and migration _context
        """
        self._connection = self._engine.connect()
        self._context = MigrationContext.configure(self._connection)

    def _close(self):
        """
        Closes down the connection
        """
        self._connection.close()
        self._connection = self._context = None


class FirmwareUpdater(object):
    def __init__(self, filename, length):
        self._filename = filename
        self._firmware_length = length
        self.completed = False
        self._upload_tick = 0
        self._wait_tick = 0

    def update(self):
        """Update the firmware."""
        try:
            self.completed = False
            self._upload_tick = 0
            self._wait_tick = 0

            # Use the Firmware utility to handle the upload
            Firmware.upload(current_app.decoder.device._device, self._filename, self._stage_callback)

        except Exception as err:
            # Log error and broadcast failure
            current_app.logger.error(f"Error updating firmware: {err}")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_ERROR', 'error': str(err)})

    def _stage_callback(self, stage, **kwargs):
        """
        Callback function that handles different stages of the firmware upload process.
        """
        if stage == Firmware.STAGE_START:
            current_app.logger.info("Beginning firmware update process..")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_START'})

        elif stage == Firmware.STAGE_WAITING:
            if self._wait_tick == 0:
                current_app.logger.debug("Waiting for device.")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_WAITING'})

        elif stage == Firmware.STAGE_BOOT:
            current_app.logger.debug("Rebooting device..")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_BOOT'})

        elif stage == Firmware.STAGE_LOAD:
            current_app.logger.debug("Waiting for boot loader..")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_LOAD'})

        elif stage == Firmware.STAGE_UPLOADING:
            if self._upload_tick == 0:
                current_app.logger.info("Uploading firmware.")
            self._upload_tick += 1

            percent = int((self._upload_tick / float(self._firmware_length)) * 100)
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_UPLOADING', 'percent': percent})

        elif stage == Firmware.STAGE_DONE:
            self.completed = True
            current_app.logger.info("Firmware upload complete!")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_DONE'})

        elif stage == Firmware.STAGE_ERROR:
            current_app.logger.error(f"Error: {kwargs.get('error', '')}")
            current_app.decoder.broadcast('firmwareupload', {'stage': 'STAGE_ERROR', 'error': kwargs.get('error', '')})

        elif stage == Firmware.STAGE_DEBUG:
            current_app.logger.debug(f"DEBUG: {kwargs.get('data', '')}")
