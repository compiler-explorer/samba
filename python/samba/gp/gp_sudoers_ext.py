# gp_sudoers_ext samba gpo policy
# Copyright (C) David Mulder <dmulder@suse.com> 2020
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from samba.gp.gpclass import gp_pol_ext, gp_file_applier
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE
from samba.gp.util.logging import log

def find_executable(executable, path):
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f):
            return f
    return None

intro = '''
### autogenerated by samba
#
# This file is generated by the gp_sudoers_ext Group Policy
# Client Side Extension. To modify the contents of this file,
# modify the appropriate Group Policy objects which apply
# to this machine. DO NOT MODIFY THIS FILE DIRECTLY.
#

'''
visudo = find_executable('visudo',
        path='%s:%s' % (os.environ['PATH'], '/usr/sbin'))

def sudo_applier_func(sudo_dir, sudo_entries):
    ret = []
    for p in sudo_entries:
        contents = intro
        contents += '%s\n' % p
        with NamedTemporaryFile() as f:
            with open(f.name, 'w') as w:
                w.write(contents)
            sudo_validation = \
                    Popen([visudo, '-c', '-f', f.name],
                        stdout=PIPE, stderr=PIPE).wait()
        if sudo_validation == 0:
            with NamedTemporaryFile(prefix='gp_',
                                    delete=False,
                                    dir=sudo_dir) as f:
                with open(f.name, 'w') as w:
                    w.write(contents)
                ret.append(f.name)
        else:
            log.error('Sudoers apply failed', p)
    return ret

class gp_sudoers_ext(gp_pol_ext, gp_file_applier):
    def __str__(self):
        return 'Unix Settings/Sudo Rights'

    def process_group_policy(self, deleted_gpo_list, changed_gpo_list,
            sdir='/etc/sudoers.d'):
        for guid, settings in deleted_gpo_list:
            if str(self) in settings:
                for attribute, sudoers in settings[str(self)].items():
                    self.unapply(guid, attribute, sudoers)

        for gpo in changed_gpo_list:
            if gpo.file_sys_path:
                section = 'Software\\Policies\\Samba\\Unix Settings\\Sudo Rights'
                pol_file = 'MACHINE/Registry.pol'
                path = os.path.join(gpo.file_sys_path, pol_file)
                pol_conf = self.parse(path)
                if not pol_conf:
                    continue
                sudo_entries = []
                for e in pol_conf.entries:
                    if e.keyname == section and e.data.strip():
                        sudo_entries.append(e.data)
                # Each GPO applies only one set of sudoers, in a
                # set of files, so the attribute does not need uniqueness.
                attribute = self.generate_attribute(gpo.name)
                # The value hash is generated from the sudo_entries, ensuring
                # any changes to this GPO will cause the files to be rewritten.
                value_hash = self.generate_value_hash(*sudo_entries)
                self.apply(gpo.name, attribute, value_hash, sudo_applier_func,
                           sdir, sudo_entries)
                # Cleanup any old entries that are no longer part of the policy
                self.clean(gpo.name, keep=[attribute])

    def rsop(self, gpo):
        output = {}
        pol_file = 'MACHINE/Registry.pol'
        if gpo.file_sys_path:
            path = os.path.join(gpo.file_sys_path, pol_file)
            pol_conf = self.parse(path)
            if not pol_conf:
                return output
            for e in pol_conf.entries:
                key = e.keyname.split('\\')[-1]
                if key.endswith('Sudo Rights') and e.data.strip():
                    if key not in output.keys():
                        output[key] = []
                    output[key].append(e.data)
        return output
