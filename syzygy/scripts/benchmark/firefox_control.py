#!/usr/bin/python2.6
"""A utility module for controlling Firefox instances."""

import re
import exceptions
import os.path
import pywintypes
import win32api
import win32con
import win32event
import win32gui
import win32process

class FirefoxNotFoundException(Exception):
  pass

class TimeoutException(Exception):
  pass

class NoPreloadingForFirefoxException(Exception):
  pass

kClassNameGeneral = 'MozillaWindowClass'
kClassNameFirefox = 'FirefoxMessageWindow'

# XXX: The Chrome version lets us pick a specific window associated with
# a profile directory.
def _FindFirefoxWindow(name):
    try:
        return win32gui.FindWindowEx(None, None, name, None)
    except pywintypes.error:
        return None

# See widget/src/windows/nsWindowDefs.h.
MOZ_WM_APP_QUIT = win32con.WM_APP + 0x0300

def locate_firefox_windows(w, data):
  cname = win32gui.GetClassName(w)
  text = win32gui.GetWindowText(w)
  # Record that we found a Firefox window.
  if (cname == kClassNameFirefox
      or (text and re.search(text, 'Mozilla Firefox'))):
    data[0] = w
  # Note the windows that we want to quit.
  if cname == kClassNameGeneral:
    data[1].append(w)

def ShutDown(profile_dir, timeout_ms=win32event.INFINITE):
  message_win = _FindFirefoxWindow(kClassNameFirefox)
  if not message_win:
    raise FirefoxNotFoundException

  # Get the thread and process IDs associated with this window.
  (thread_id, process_id) = win32process.GetWindowThreadProcessId(message_win)

  # Open the process in question, so we can wait for it to exit.
  permissions = win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION
  process_handle = win32api.OpenProcess(permissions, False, process_id)

  data = [ None, [] ]
  win32gui.EnumThreadWindows(thread_id, locate_firefox_windows, data)
  if data[0]:
    for kw in data[1]:
      win32gui.PostMessage(kw, MOZ_WM_APP_QUIT)

  result = win32event.WaitForSingleObject(process_handle, timeout_ms)
  exit_status = win32process.GetExitCodeProcess(process_handle)
  process_handle.Close()

  # Raise if it didn't exit in time.
  if result != win32event.WAIT_OBJECT_0:
    raise TimeoutException

  return exit_status

# XXX: no way to ask for a particular Firefox with profile_dir.
def IsProfileRunning(profile_dir):
  if _FindFirefoxWindow(kClassNameFirefox):
    return True
  return False

# XXX: Not needed for Firefox?  Do we even try preloading?
def GetPreload():
  return (False, None, None)

def SetPreload(enable, size=None, stride=None):
  if enable:
    raise NoPreloadingForFirefoxException
