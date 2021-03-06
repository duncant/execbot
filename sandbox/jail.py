import sys, os, subprocess
from collections import deque

from pid import PidProc
from rpython.translator.sandbox.sandlib import VirtualizedSandboxedProc
from sandbox.pipe import PipeProc
from rpython.translator.sandbox.vfs import Dir, RealDir, RealFile
LIB_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.__file__)))

def go_to_jail(chroot_path, jail_uid, jail_gid):
    # chroot
    os.chdir(chroot_path)
    os.chroot(chroot_path)

    # drop privs
    os.setgroups([])
    os.setgid(jail_gid)
    os.setuid(jail_uid)

class JailedProc(PidProc, VirtualizedSandboxedProc, PipeProc):
    def __init__(self, sandbox_args, executable, heap_size, uid, gid,
                 tmppath=None, chroot=None, procdir=None, p_table=None):
        sandbox_args = ('-S', '--heapsize', str(heap_size)) + tuple(sandbox_args)
        chroot = os.path.abspath(chroot) if chroot is not None else None

        # from PidProc
        self.p_table = p_table

        # from VirtualizedSandboxedProc, with modifications
        execpath = os.path.abspath(executable)
        tmppath = os.path.abspath(tmppath) if tmppath is not None else None
        self.virtual_root = self.build_virtual_root(tmppath, execpath, procdir)
        self.open_fds = {}

        # from PipeProc
        self.inbuf = deque()
        self.inpos = None
        self.outbuf = []
        self.outsiz = 0
        self.errbuf = []
        self.errsiz = 0

        # from SandboxedProc, with modifications
        self.popen = subprocess.Popen(sandbox_args, executable=execpath,
                                      bufsize=-1,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      preexec_fn=lambda:go_to_jail(chroot, uid, gid),
                                      close_fds=True,
                                      cwd=(chroot if chroot is not None else '.'),
                                      env={})
        self.popenlock = None
        self.currenttimeout = None
        self.currentlyidlefrom = None

    @staticmethod
    def build_virtual_root(tmppath, execpath, procdir):
        exclude = ['.pyc', '.pyo']
        if tmppath is None:
            tmpdirnode = Dir({})
        else:
            tmpdirnode = RealDir(tmppath, exclude=exclude)
        libroot = str(LIB_ROOT)

        return Dir({
            'usr': Dir({
                'include' : RealDir(os.path.join(os.sep, 'usr', 'include'),
                                   exclude=exclude)
                }),
            'bin': Dir({
                'pypy-c': RealFile(execpath),
                'lib-python': RealDir(os.path.join(libroot, 'lib-python'),
                                      exclude=exclude),
                'lib_pypy': RealDir(os.path.join(libroot, 'lib_pypy'),
                                      exclude=exclude),
                }),
             'tmp': tmpdirnode,
             'proc': procdir if procdir is not None else Dir({}),
             })

__all__ = ["JailedProc"]
