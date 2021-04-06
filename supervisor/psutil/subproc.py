# coding=utf-8
import ctypes
import os
import signal
import subprocess
import sys
from subprocess import list2cmdline

import pywintypes
import win32api
import win32con
import win32event
import win32gui
import win32process
import win32security

from supervisor.compat import as_string


class LoginSTARTUPINFO(object):
	"""
	Special STARTUPINFO instance that carries login credentials. When a
	LoginSTARTUPINFO instance is used with Popen, the process will be executed
	with the credentials used to instantiate the class.

	If an existing vanilla STARTUPINFO instance needs to be converted, it
	can be supplied as the last parameter when instantiating LoginSTARTUPINFO.

	The LoginSTARTUPINFO cannot be used with the regular subprocess module.
	"""

	def __init__(self, username, password, domain=None, startupinfo=None):
		# Login credentials
		self.credentials = (username, domain, password)
		self.startupinfo = startupinfo

	@property
	def win32startupinfo(self):
		win32startupinfo = win32process.STARTUPINFO()
		if self.startupinfo:
			win32startupinfo.dwFlags = self.startupinfo.dwFlags
			win32startupinfo.wShowWindow = self.startupinfo.wShowWindow
			win32startupinfo.hStdInput = int(self.startupinfo.hStdInput)
			win32startupinfo.hStdOutput = int(self.startupinfo.hStdOutput)
			win32startupinfo.hStdError = int(self.startupinfo.hStdError)
		return win32startupinfo


class Popen(subprocess.Popen):
	"""
	Opens a new process (just as subprocess), but lets you know when the
	process was killed (using the kill attribute).
	"""

	@property
	def message(self):
		if self.returncode is None:
			return 'still running'
		if self.returncode == 0:
			msg = "termination normal"
		elif self.returncode < 0:
			msg = "termination by signal"
		else:
			msg = "exit status %s" % (self.returncode,)
		return msg

	def check_win32api_status(self, status):
		if status == 0:
			status = win32api.FormatMessage(win32api.GetLastError())
			status = as_string(status, errors='ignore')
			status = status.strip('\r\n')
		return status

	def send_os_signal(self, sig, proc_name):
		"""Send signal by GenerateConsoleCtrlEvent"""
		status = ctypes.windll.kernel32.GenerateConsoleCtrlEvent(sig, self.pid)
		status = self.check_win32api_status(status)
		return "signal: %s (status %s)" % (proc_name, status)

	def send_win_signal(self, sig, proc_name):
		window = []

		# callback for handling window search
		def check_window(hwnd, window):
			_, pid = win32process.GetWindowThreadProcessId(hwnd)
			if pid == self.pid:
				window.append(hwnd)
				return False
			return True

		# find window
		try:
			win32gui.EnumWindows(check_window, window)
		except pywintypes.error:
			# Exception is raised by terminating search early (if a window is found)
			# Ignore it!
			pass

		if window:
			status = win32api.PostMessage(window[0], sig, None, None)
			status = self.check_win32api_status(status)
		else:
			status = "failed to find window to send signal"
		return "win signal: %s (status %s)" % (proc_name, status)

	def kill2(self, sig, as_group=False, proc_name=None):
		if as_group:
			return self.taskkill()
		elif sig in [signal.CTRL_BREAK_EVENT, signal.CTRL_C_EVENT]:
			return self.send_os_signal(sig, proc_name)
		elif sig < 0:
			return self.send_win_signal(-sig, proc_name)
		else:
			return self.send_signal(sig)

	def taskkill(self):
		"""Kill process group"""
		output = subprocess.check_output(['taskkill',
										  '/PID', str(self.pid),
										  '/F', '/T'])
		return as_string(output, encoding=sys.getfilesystemencoding(), errors='ignore').strip()


class WPopen(Popen):
	"""
	Opens a process in the context of a user.

	startupinfo = LoginSTARTUPINFO(username, password, domain)
	WPopen(startupinfo=startupinfo)
	"""

	@staticmethod
	def _logon_user(username, domain, password):
		"""Login as specified user and return handle."""
		token = win32security.LogonUser(
			username, domain, password,
			win32con.LOGON32_LOGON_INTERACTIVE,
			win32con.LOGON32_PROVIDER_DEFAULT
		)
		return token

	def _internal_poll(self, **kwargs):
		kwargs['_WaitForSingleObject'] = win32event.WaitForSingleObject
		kwargs['_WAIT_OBJECT_0'] = win32con.WAIT_OBJECT_0
		kwargs['_GetExitCodeProcess'] = win32process.GetExitCodeProcess
		return super()._internal_poll(**kwargs)

	def terminate(self):
		"""Terminates the process."""
		# Don't terminate a process that we know has already died.
		if self.returncode is not None:
			return
		try:
			win32process.TerminateProcess(self._handle, 1)
		except PermissionError:
			# ERROR_ACCESS_DENIED (winerror 5) is received when the
			# process already died.
			rc = win32process.GetExitCodeProcess(self._handle)
			if rc == win32con.STILL_ACTIVE:
				raise
			self.returncode = rc

	kill = terminate

	def _execute_child(self,
					   args, executable,
					   preexec_fn, close_fds,
					   pass_fds, cwd, env,
					   startupinfo, creationflags, shell,
					   p2cread, p2cwrite,
					   c2pread, c2pwrite,
					   errread, errwrite,
					   unused_restore_signals,
					   unused_start_new_session):
		"""Execute program (MS Windows version)"""

		assert not pass_fds, "pass_fds not supported on Windows."
		assert isinstance(startupinfo, LoginSTARTUPINFO), ""

		if not isinstance(args, str):
			args = list2cmdline(args)

		win32startupinfo = startupinfo.win32startupinfo

		use_std_handles = -1 not in (p2cread, c2pwrite, errwrite)
		if use_std_handles:
			win32startupinfo.dwFlags |= win32con.STARTF_USESTDHANDLES
			win32startupinfo.hStdInput = p2cread
			win32startupinfo.hStdOutput = c2pwrite
			win32startupinfo.hStdError = errwrite

		if shell:
			win32startupinfo.dwFlags |= win32con.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = win32con.SW_HIDE
			comspec = os.environ.get("COMSPEC", "cmd.exe")
			args = '{} /c "{}"'.format(comspec, args)

		token = self._logon_user(*startupinfo.credentials)
		# Start the process
		try:
			hp, ht, pid, tid = win32process.CreateProcessAsUser(token,
																executable, args,
																# no special security
																None, None,
																int(not close_fds),
																creationflags,
																env,
																os.fspath(cwd) if cwd is not None else None,
																win32startupinfo)
		finally:
			token.close()
			# Child is launched. Close the parent's copy of those pipe
			# handles that only the child should have open.  You need
			# to make sure that no handles to the write end of the
			# output pipe are maintained in this process or else the
			# pipe will not close when the child process exits and the
			# ReadFile will hang.
			if p2cread != -1:
				p2cread.Close()
			if c2pwrite != -1:
				c2pwrite.Close()
			if errwrite != -1:
				errwrite.Close()
			if hasattr(self, '_devnull'):
				os.close(self._devnull)
			# Prevent a double close of these handles/fds from __init__
			# on error.
			self._closed_child_pipe_fds = True

		# Retain the process handle, but close the thread handle
		self._child_created = True
		self._handle = hp
		self.pid = pid
		ht.close()
