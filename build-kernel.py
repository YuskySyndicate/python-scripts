# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2019 Adek Maulana

from __future__ import print_function

import sys
import os
import signal
import psutil
from datetime import datetime
from argparse import ArgumentParser
from subprocess import Popen, PIPE
from os import remove, chdir
from os.path import exists, isfile, expanduser, join, realpath  # , isdir
from tempfile import mkstemp


def dt():
    startTime = datetime.now()
    date_time = datetime.now().strftime('%Y%m%d-%H%M')
    return {
        'date-version': date_time,
        'start': startTime
    }


def parameters():
    param = ArgumentParser(description='Kernel Build Script.', )
    param.add_argument('-b', '--build',
                       choices=['miui', 'custom'], required=True)
    param.add_argument('-c', '--cpuquiet', action='store_true')
    param.add_argument('-d', '--device',
                       choices=['mido', 'whyred'], required=True)
    param.add_argument('-o', '--overclock',
                       help='use this flag to enable overclock',
                       action='store_true')
    param.add_argument('-r', '--release',
                       help='use this flag to enable release build',
                       action='store_true')
    param.add_argument('-t', '--telegram',
                       help='use this flag to enable telegram report',
                       action='store_true')
    param.add_argument('-u', '--upload',
                       help='use this flag to upload the build',
                       action='store_true')
    param.add_argument('--verbose', action='store_true')
    param.add_argument('-v', '--version', required=True)
    param.add_argument('-cc', '--cc', choices=['clang', 'gcc'], required=True)
    params = vars(param.parse_args())
    build_type = params['build']
    cpuquiet = params['cpuquiet']
    device = params['device']
    oc = params['overclock']
    release = params['release']
    telegram = params['telegram']
    upload = params['upload']
    verbose = params['verbose']
    version = params['version']
    cc = params['cc']
    # Check whyred ENV
    if device == 'whyred':
        if cpuquiet:
            print('whyred do not have cpuquiet.')
            cpuquiet = False
        if oc:
            print('whyred do not have overclock.')
            oc = False
        if build_type == 'custom':
            print('whyred customROM already dead.')
            build_type = 'miui'
    elif device == 'mido':
        if cpuquiet is False:
            print('mido already drop support for non-cpuquiet\n'
                  'default now is using it.')
            cpuquiet = True
    # Fail build if using version beta|test|personal while using --release
    if version in ['beta' or 'test' or 'personal'] and release is True:
        err('version beta|test|personal, can not be passed with --release')
        sys.exit(1)
    return {
        'type': build_type,
        'cpuquiet': cpuquiet,
        'device': device,
        'overclock': oc,
        'release': release,
        'telegram': telegram,
        'upload': upload,
        'verbose': verbose,
        'version': version,
        'cc': cc
    }


def subprocess_run(cmd):
    global exitCode
    verbose = parameters()['verbose']
    if verbose is True:
        stdout_val = sys.stdout
        stderr_val = sys.stderr
    else:
        stdout_val = PIPE
        stderr_val = PIPE
    subproc = Popen(cmd, stdout=stdout_val, stderr=stderr_val,
                    shell=True, universal_newlines=True)
    subproc.wait()
    talk = subproc.communicate()
    exitCode = subproc.returncode
    if exitCode != 0 and verbose is not True:
        err('An error was detected while running the subprocess:\n'
            f'cmd: {cmd}\n'
            f'exit code: {exitCode}\n'
            f'stdout: {talk[0]}\n'
            f'stderr: {talk[1]}')  # % exitCode, talk[0], talk[1]))
    elif exitCode != 0 and verbose is True:
        err('An error was detected while running the subprocess:\n'
            f'cmd: {cmd}\n')
    return talk


def err(message):
    print(message)
    telegram = parameters()['telegram']
    home = variables()['home']
    if telegram is True:
        from requests import post
        tg_chat = '-1001354431412'
        token = open(home + '/token', 'r').read().splitlines()[0]
        tmp = mkstemp()
        msgtmp = tmp[1]
        with open(msgtmp, 'w', newline='\n') as t:
            t.write('```')
            t.write('\n')
            t.write('An error was detected while running '
                    'the following command:')
            t.writelines('\n' + '\n')
            t.write(' '.join(sys.argv[0:]))
            t.writelines('\n' + '\n')
            t.write('The error was:')
            t.writelines('\n' + '\n')
            t.write(f'{message}')
            t.write('\n')
            t.write('```')
        with open(msgtmp, 'r') as t:
            messages = (
                ('chat_id', tg_chat),
                ('text', t.read()),
                ('parse_mode', 'Markdown'),
                ('disable_notification', 'no'),
                ('disable_web_page_preview', 'yes')
            )
        tg = 'https://api.telegram.org/bot' + token + '/sendMessage'
        telegram = post(tg, params=messages)
        if telegram.status_code == 200:
            print('Messages sent...')
        elif telegram.status_code == 400:
            print('Bad recipient / Wrong text format...')
        elif telegram.status_code == 401:
            print('Wrong / Unauth token...')
        else:
            print('Error out of range...')
        print(telegram.reason)
        remove(msgtmp)


def kill_subprocess(parent_pid, sig=signal.SIGTERM):
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for process in children:
        process.send_signal(sig)


def variables():
    device = parameters()['device']
    build_type = parameters()['type']
    version = parameters()['version']
    oc = parameters()['overclock']
    cpuquiet = parameters()['cpuquiet']
    date_time = dt()['date-version']
    home = expanduser('~')
    rundir = os.getcwd()
    scriptdir = realpath(sys.argv[0]).split(f'/{sys.argv[0]}')[0]
    kerneldir = join(home, 'kernel')
    sourcedir = join(kerneldir, f'{device}')
    anykernel = join(kerneldir, f'anykernel/{device}/{build_type}')
    outdir = join(kerneldir, f'build/out/target/kernel/{device}/{build_type}')
    zipdir = join(kerneldir,
                  f'build/out/target/kernel/zip/{device}/{build_type}')
    image = join(outdir, 'arch/arm64/boot/Image.gz-dtb')
    tcdir = join(kerneldir, 'toolchain')
    keystore_password = open(home + '/keystore_password', 'r'
                             ).read().splitlines()[0].split('=')[1]
    afh_password = open(home + '/pass', 'r').read().splitlines()[0]
    if device == 'whyred':
        defconfig = 'whyred_defconfig'
        version = version + '-' + 'MIUI'
        name = 'Stormguard' + '-' + device + '-' + version + '-' + date_time
        branch = 'R/O/MIUI'
        moduledir = join(anykernel, 'modules/vendor/lib/modules')
    elif device == 'mido':
        name = 'Stormguard'
        defconfig = 'sg_defconfig'
        if oc is True:
            name = name + '-' + 'OC'
        if cpuquiet is True:
            zipdir = join(zipdir, 'CPUQuiet')
            name = name + '-' + 'CPUQuiet'
        if build_type == 'miui':
            branch = 'R/N/MIUI'
            version = version + '-' + 'MIUI'
            moduledir = join(anykernel, 'modules/system/lib/modules')
        elif build_type == 'custom':
            branch = 'R/C/P'
            version = version + '-' + 'CUSTOM'
        name = name + '-' + device + '-' + version + '-' + date_time
    zipname = name + '.zip'
    finalzip = join(zipdir, zipname)
    return {
        'anykernel': anykernel,
        'branch': branch,
        'afh': afh_password,
        'defconfig': defconfig,
        'finalzip': finalzip,
        'home': home,
        'image': image,
        'keystore': keystore_password,
        'moduledir': moduledir,
        'outdir': outdir,
        'rundir': rundir,
        'scriptdir': scriptdir,
        'sourcedir': sourcedir,
        'tcdir': tcdir,
        'zipdir': zipdir
    }


def toolchain():
    tcdir = variables()['tcdir']
    cc = parameters()['cc']
    gcc = join(tcdir, 'google-gcc/bin/aarch64-linux-android-')
    gcc32 = join(tcdir, 'google-gcc-32/bin/arm-linux-androideabi-')
    tcstrip = join(tcdir, 'google-gcc/bin/aarch64-linux-android-strip')
    if cc == 'clang':
        clang = join(tcdir, 'google-clang/bin/clang')
        clangcc = ' '.join(['ccache', clang])
        clang_version = (f'$({clang} --version | head -n 1 | '
                         r'perl -pe "s/\(http.*?\)//gs" | '
                         'sed -e "s/  */ /g" -e "s/[[:space:]]*$//" | '
                         'cut -d " " -f-1,6-8)')
        cmd = f'echo "{clang_version}"'
        talk = subprocess_run(cmd)
        clang_version = talk[0].strip('\n')
        clangopt = ' '.join([f'CC="{clangcc}"',
                             'CLANG_TRIPLE="aarch64-linux-gnu-"',
                             'CLANG_TRIPLE_ARM32="arm-linux-gnueabi-"',
                             'KBUILD_COMPILER_STRING="{clang_version}"'])
    return {
        'gcc': gcc,
        'gcc32': gcc32,
        'strip': tcstrip,
        'clang': clang,
        'clangcc': clangcc,
        'clangopt': clangopt,
        'clang_version': clang_version
    }


def make():
    build_type = parameters()['type']
    oc = parameters()['overclock']
    outdir = variables()['outdir']
    device = parameters()['device']
    defconfig = variables()['defconfig']
    sourcedir = variables()['sourcedir']
    branch = variables()['branch']
    cc = parameters()['cc']
    gcc = toolchain()['gcc']
    gcc32 = toolchain()['gcc32']
    clangopt = toolchain()['clangopt']
    chdir(sourcedir)
    '''
    mido now drop support for non-CPUQuiet
    because, now we can change default max cpu,
    so for people who wanted without CPUQuiet
    they can changed max online cpu to 8, or just change
    CPUQuiet governor to userspace, and turn on all offlined cpu
    '''
    cmd = f'git checkout {branch}'
    talk = subprocess_run(cmd)
    if device == 'mido':
        if oc is False:
            revert_commit = {
                'custom': 'None',  # Haven't have time to rebase PIE
                'miui': '122cc6988b399885ea8918a790c01662a20e8463'
            }
            if build_type == 'miui':
                cmd = f'git revert --no-commit {revert_commit["miui"]}'
            elif build_type == 'custom':
                cmd = f'git revert --no-commit {revert_commit["custom"]}'
            talk = subprocess_run(cmd)
            if exitCode != 0:
                return False
    cmd = f'make ARCH=arm64 O="{outdir}" {defconfig}'
    talk = subprocess_run(cmd)
    if cc == 'clang':
        cmd = (f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="{gcc}" '
               f'CROSS_COMPILE_ARM32="{gcc32}" -j4 {clangopt}')
    elif cc == 'gcc':
        cmd = (f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="ccache {gcc}'
               f'CROSS_COMPILE_ARM32="ccache {gcc32}" -j4')
    talk = subprocess_run(cmd)
    if exitCode != 0:
        raise ChildProcessError
        '''
        TO-DO, clean and restart build if make fail asking `make mrproper`
        if exists(join(sourcedir, 'include/config')
                  ) and isdir(join(sourcedir, 'include/config')):
            cmd = 'make mrproper'
            talk = subprocess_run(cmd)
            return make()
        '''
    else:
        print('success')

def modules():
    None
    #  TO-DO


def zip_kernel():
    None
    #   TO-DO


def googledrive_creds():
    scriptdir = variables()['scriptdir']
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle

    SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    creds = None
    if exists(join(scriptdir, 'token.pickle')
              ) and isfile(join(scriptdir, 'token.pickle')):
        with open(join(scriptdir, 'token.pickle'), 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                join(scriptdir, 'credential.json'), SCOPES)
            creds = flow.run_local_server()
        with open(join(scriptdir, 'token.pickle'), 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service


def googledrive_upload():
    service = googledrive_creds()
    folder = {
        'cpuquiet': '1i5XRVcO3Q8y8OFAOxXU-UWGWmQJiKo2u',
        'whyred': '1YjsSb1JYqWOANua07kd_UN4q2vPoq1iv',
        'mido': '1fkEmVBKD0cHMY1kbkpr4Bwm9v3COPPjf'
    }
    #  TO-DO


def afh_upload():
    None
    #  TO-DO


def uploads():
    None
    #  TO-DO


parameters()
make()
