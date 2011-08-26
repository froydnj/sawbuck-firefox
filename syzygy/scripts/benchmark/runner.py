#!/usr/bin/python2.6
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility classes and functions to run benchmarks on Chrome execution and
extract metrics from ETW traces."""

import chrome_control
import firefox_control
import ctypes
import ctypes.wintypes
import etw
import etw_db
import etw.evntrace as evn
import event_counter
import exceptions
import glob
import logging
import os.path
import pkg_resources
import re
import shutil
import subprocess
import sys
import tempfile
import time
import win32api


# The Windows prefetch directory, this is possibly only valid on Windows XP.
_PREFETCH_DIR = os.path.join(os.environ['WINDIR'], 'Prefetch')


# Set up a file-local logger.
_LOGGER = logging.getLogger(__name__)


_XP_MAJOR_VERSION = 5


class RunnerError(Exception):
  """Exceptions raised by this module are instances of this class."""
  pass


def _DeletePrefetch():
  """Deletes all files that start with Chrome.exe in the OS prefetch cache.
  """
  files = glob.glob('%s\\Chrome.exe*.pf' % _PREFETCH_DIR)
  _LOGGER.info("Deleting %d prefetch files", len(files))
  for file in files:
    os.unlink(file)


def _GetExePath(name):
  '''Gets the path to a named executable.'''
  path = pkg_resources.resource_filename(__name__, os.path.join('exe', name))
  if not os.path.exists(path):
    # If we're not running packaged from an egg, we assume we're being
    # run from a virtual env in a build directory.
    build_dir = os.path.abspath(os.path.join(os.path.dirname(sys.executable),
                                             '../..'))
    path = os.path.join(build_dir, name)
  return path


def _GetRunInSnapshotExeResourceName():
  """Return the name of the most appropriate run_in_snapshot executable for
  the system we're running on."""
  maj, min = sys.getwindowsversion()[:2]
  # 5 is XP.
  if maj == _XP_MAJOR_VERSION:
    return 'run_in_snapshot_xp.exe'
  if maj < _XP_MAJOR_VERSION:
    raise RunnerError('Unrecognized system version.')

  # We're on Vista or better, pick the 32 or 64 bit version as appropriate.
  is_wow64 = ctypes.wintypes.BOOL()
  is_wow64_function = ctypes.windll.kernel32.IsWow64Process
  if not is_wow64_function(win32api.GetCurrentProcess(),
                           ctypes.byref(is_wow64)):
    raise Exception('IsWow64Process failed.')
  if is_wow64:
    return 'run_in_snapshot_x64.exe'

  return 'run_in_snapshot.exe'


def _GetRunInSnapshotExe():
  """Return the appropriate run_in_snapshot executable for this system."""
  return _GetExePath(_GetRunInSnapshotExeResourceName())


class ChromeRunner(object):
  """A utility class to manage the running of Chrome for some number of
  iterations."""

  @staticmethod
  def StartLogging(log_dir):
    """Starts ETW Logging to the files provided.

    Args:
        log_dir: Directory where kernel.etl and call_trace.etl will be created.
    """
    # Best effort cleanup in case the log sessions are already running.
    subprocess.call([_GetExePath('call_trace_control.exe'), 'stop'])

    kernel_file = os.path.abspath(os.path.join(log_dir, 'kernel.etl'))
    call_trace_file = os.path.abspath(os.path.join(log_dir, 'call_trace.etl'))
    cmd = [_GetExePath('call_trace_control.exe'),
           'start',
           '--kernel-file=%s' % kernel_file,
           '--call-trace-file=%s' % call_trace_file]
    _LOGGER.info('Starting ETW logging to "%s" and "%s".',
        kernel_file, call_trace_file)
    ret = subprocess.call(cmd)
    if ret != 0:
      raise RunnerError('Failed to start ETW logging.')

  @staticmethod
  def StopLogging():
    cmd = [_GetExePath('call_trace_control.exe'), 'stop']
    _LOGGER.info('Stopping ETW logging.')
    ret = subprocess.call(cmd)
    if ret != 0:
      raise RunnerError('Failed to stop ETW logging.')

  def __init__(self, chrome_exe, profile_dir, initialize_profile=True):
    """Initialize instance.

    Args:
        chrome_exe: path to the Chrome executable to benchmark.
        profile_dir: path to the profile directory for Chrome.
        initialize_profile: if True, the profile directory will be erased and
            Chrome will be launched once to initialize it.
    """
    self._chrome_exe = chrome_exe
    self._profile_dir = profile_dir
    self._initialize_profile = initialize_profile
    if re.search('chrome', chrome_exe):
      self._controller = chrome_control
    else:
      self._controller = firefox_control

  def Run(self, iterations):
    """Runs the benchmark for a given number of iterations.

    Args:
        iterations: number of iterations to run.
    """
    self._SetUp()

    try:
      # Run the benchmark for the number of iterations specified.
      for i in range(iterations):
        _LOGGER.info("Starting iteration %d", i)
        self._PreIteration(i)
        self._RunOneIteration(i)
        self._PostIteration(i)

      # Output the results after completing all iterations.
      self._ProcessResults()
    except:
      _LOGGER.exception('Failure in iteration %d.', i)
    finally:
      self._TearDown()

  def _SetUp(self):
    """Invoked once before a set of iterations."""
    if self._controller.IsProfileRunning(self._profile_dir):
      _LOGGER.warning(
          'Chrome already running in profile "%s", shutting it down.',
          self._profile_dir)
      self._controller.ShutDown(self._profile_dir)

    if self._initialize_profile:
      shutil.rmtree(self._profile_dir, True)

    if not os.path.isdir(self._profile_dir):
      self._InitializeProfileDir()

  def _TearDown(self):
    """Invoked once after all iterations are complete, or on failure."""
    pass

  def _RunOneIteration(self, i):
    """Perform the iteration."""
    _LOGGER.info("Iteration: %d", i)

    self._LaunchChrome()

    self._WaitTillChromeRunning()
    self._DoIteration(i)

    _LOGGER.info("Shutting down Chrome Profile: %s", self._profile_dir)
    self._controller.ShutDown(self._profile_dir)

  def _DoIteration(self, it):
    """Invoked each iteration after Chrome has successfully launched."""
    pass

  def _PreIteration(self, it):
    """Invoked prior to each iteration."""
    pass

  def _PostIteration(self, i):
    """Invoked after each successfull iteration."""
    pass

  def _ProcessResults(self):
    """Invoked after all iterations have succeeded."""
    pass

  def _LaunchChrome(self, extra_arguments=None):
    """Launch the Chrome instance for this iteration."""
    self._LaunchChromeImpl(extra_arguments)

  def _LaunchChromeImpl(self, extra_arguments=None):
    """Launch a Chrome instance in our profile dir, with extra_arguments."""
    cmd_line = [self._chrome_exe]
    # XXX hack due to different profile functionality
    if self._controller == chrome_control:
      cmd_line.extend(['--user-data-dir=%s' % self._profile_dir])
    else:
      if '-CreateProfile' not in extra_arguments:
        cmd_line.extend(['-profile', self._profile_dir])
    if extra_arguments:
      cmd_line.extend(extra_arguments)

    _LOGGER.info('Launching command line [%s].', cmd_line)
    subprocess.Popen(cmd_line)

  def _InitializeProfileDir(self):
    """Initialize a Chrome profile directory by launching, then stopping
    Chrome in that directory.
    """
    _LOGGER.info('Initializing profile dir "%s".', self._profile_dir)
    # XXX hack due to different profile initialization functionality
    if self._controller == chrome_control:
      self._LaunchChromeImpl(['--no-first-run'])
      self._WaitTillChromeRunning()
      self._controller.ShutDown(self._profile_dir)
    else:
      self._LaunchChromeImpl(['-CreateProfile', self._profile_dir])

  def _WaitTillChromeRunning(self):
    """Wait until Chrome is running in our profile directory.

    Raises:
        RunnerError if Chrome is not running after a 5 minute wait.
    """
    # Use a long timeout just in case the machine is REALLY bogged down.
    # This could be the case on the builtbot slave, for example.
    for i in xrange(300):
      if self._controller.IsProfileRunning(self._profile_dir):
        return
      time.sleep(1)

    raise RunnerError('Timeout waiting for Chrome.')


class BenchmarkRunner(ChromeRunner):
  """A utility class to manage the running of Chrome startup time benchmarks.

  This class can run a given Chrome instance through a few different
  configurable scenarios:
    * With Chrome.dll preloading turned on or turned off.
    * Cold/Warm start. To simulate cold start, the volume containing the
      Chrome executable under test will be remounted to a new drive letter
      using the Windows shadow volume service.
    * With Windows XP OS prefetching enabled or disabled.
  """

  def __init__(self, chrome_exe, profile_dir, preload, cold_start, prefetch,
               keep_temp_dirs):
    """Initialize instance.

    Args:
        chrome_exe: path to the Chrome executable to benchmark.
        profile_dir: path to the existing profile directory for Chrome.
        preload: specifies the state of Chrome.dll preload to use for
            benchmark.
        cold_start: if True, chrome_exe will be launched from a shadow volume
            freshly minted and mounted for each iteration.
        prefetch: if False, the OS prefetch files will be deleted before and
            after each iteration.
        keep_temp_dirs: if True, the script will not clean up the temporary
            directories it creates. This is handy if you want to e.g. manually
            inspect the log files generated.
    """
    super(BenchmarkRunner, self).__init__(chrome_exe, profile_dir)
    self._preload = preload
    self._cold_start = cold_start
    self._prefetch = prefetch
    self._keep_temp_dirs = keep_temp_dirs
    self._results = {}
    self._temp_dir = None

  def _SetUp(self):
    super(BenchmarkRunner, self)._SetUp()
    self._old_preload = self._controller.GetPreload()
    self._controller.SetPreload(self._preload)
    self._temp_dir = tempfile.mkdtemp(prefix='chrome-bench')
    _LOGGER.info('Created temporary directory "%s".', self._temp_dir)

  def _TearDown(self):
    self._controller.SetPreload(*self._old_preload)
    if self._temp_dir and not self._keep_temp_dirs:
      _LOGGER.info('Deleting temporary directory "%s".', self._temp_dir)
      shutil.rmtree(self._temp_dir, ignore_errors=True)
      self._temp_dir = None
    super(BenchmarkRunner, self)._TearDown()

  def _LaunchChrome(self):
    if self._cold_start:
      (drive, path) = os.path.splitdrive(self._chrome_exe)
      chrome_exe = os.path.join('M:', path)
      run_in_snapshot = _GetRunInSnapshotExe()
      cmd_line = [run_in_snapshot,
                  '--volume=%s\\' % drive,
                  '--snapshot=M:',
                  '--',
                  chrome_exe,
                  '--user-data-dir=%s' % self._profile_dir]
    else:
      cmd_line = [self._chrome_exe,
                  '--user-data-dir=%s' % self._profile_dir]

    _LOGGER.info('Launching command line [%s].', cmd_line)
    subprocess.Popen(cmd_line)

  def _DoIteration(self, it):
    # Give our Chrome instance 10 seconds to settle.
    time.sleep(10)

  def _PreIteration(self, i):
    self._StartLogging()
    if not self._prefetch:
      _DeletePrefetch()

  def _PostIteration(self, i):
    self._StopLogging()
    self._ProcessLogs()

    if not self._prefetch:
      _DeletePrefetch()

  def _StartLogging(self):
    self.StartLogging(self._temp_dir)
    self._kernel_file = os.path.join(self._temp_dir, 'kernel.etl')

  def _StopLogging(self):
    self.StopLogging()

  def _ProcessLogs(self):
    parser = etw.consumer.TraceEventSource()
    parser.OpenFileSession(self._kernel_file)

    file_db = etw_db.FileNameDatabase()
    module_db = etw_db.ModuleDatabase()
    process_db = etw_db.ProcessThreadDatabase()
    counter = event_counter.LogEventCounter(self._chrome_exe, file_db,
                                            module_db, process_db)
    parser.AddHandler(file_db)
    parser.AddHandler(module_db)
    parser.AddHandler(process_db)
    parser.AddHandler(counter)
    parser.Consume()

    name = os.path.basename(self._chrome_exe)
    # TODO(siggi): Other metrics, notably:
    #   Time from launch of browser to interesting TRACE_EVENT metrics
    #     in browser and renderers.
    self._AddResult(name, 'HardPageFaults', counter._hardfaults)
    self._AddResult(name, 'SoftPageFaults', counter._softfaults)

    if counter._process_launch and len(counter._process_launch) >= 2:
      browser_start = counter._process_launch.pop(0)
      renderer_start = counter._process_launch.pop(0)
      self._AddResult(name,
                      'RendererLaunchTime',
                      renderer_start - browser_start,
                      's')

    # We leave it to TearDown to delete any files we've created.
    self._kernel_file = None

  def _ProcessResults(self):
    """Outputs the benchmark results in the format required by the
    GraphingLogProcessor class, which is:

    RESULT <graph name>: <trace name>= [<comma separated samples>] <units>

    Example:
      RESULT Chrome: RendererLaunchTime= [0.1, 0.2, 0.3] s
    """
    for (key, value) in self._results.iteritems():
      (graph_name, trace_name) = key
      (units, results) = value
      print "RESULT %s: %s= %s %s" % (graph_name, trace_name,
                                      str(results), units)

  def _AddResult(self, graph_name, trace_name, sample, units=''):
    _LOGGER.info("Adding result %s, %s, %s, %s",
                 graph_name, trace_name, str(sample), units)
    results = self._results.setdefault((graph_name, trace_name), (units, []))
    results[1].append(sample)
