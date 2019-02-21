# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2019 Adek Maulana

import sys
import os
import signal
import psutil
from datetime import datetime
from argparse import ArgumentParser
from subprocess import Popen, PIPE, CalledProcessError
from os import remove, chdir
from os.path import exists, isfile, expanduser, join, realpath, isdir
from shutil import copy2 as copy
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
    param.add_argument('--verbose',
                       help='choose output of stdout and stderr, PIPE'
                            'or realtime output',
                       action='store_true')
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
        # Let's fail all of this if depencies are met, because i'm stupid.
        if True in [cpuquiet, oc, build_type]:
            param.error('\n'
                        '[-c/--cpuquiet, -o/--overclock, -b/--build = custom]'
                        ', is not available for whyred')
    elif device == 'mido':
        if cpuquiet is False:
            param.error('mido already drop support for non-cpuquiet,\n'
                        'default now is using it.')
    # Fail build if using version beta|test|personal while using --release
    if version in ['beta' or 'test' or 'personal'] and release is True:
        param.error('version beta|test|personal, '
                    'can not be passed with --release')
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
        raise CalledProcessError(cmd, 'An error was detected while '
                                 'running the subprocess:\n'
                                 f'cmd: {cmd}\n'
                                 f'exit code: {exitCode}\n'
                                 f'stdout: {talk[0]}\n'
                                 f'stderr: {talk[1]}')
    elif exitCode != 0 and verbose is True:
        raise CalledProcessError(cmd, 'An error was detected while running the'
                                 ' subprocess:\n'
                                 f'cmd: {cmd}')
    return talk


def err(message):
    print(message)
    telegram = parameters()['telegram']
    home = variables()['home']
    verbose = parameters()['verbose']
    if telegram is True:
        from requests import post
        tg_chat = '-1001354431412'
        token = open(home + '/token', 'r').read().splitlines()[0]
        tmp = mkstemp()
        msgtmp = tmp[1]
        with open(msgtmp, 'w', newline='\n') as t:
            t.write('```')
            t.writelines('\n')
            t.write('Error found while running:')
            t.writelines('\n' + '\n')
            t.write(' '.join(sys.argv[0:]))
            t.writelines('\n' + '\n')
            t.write(f'{message}')
            t.writelines('\n')
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
        if verbose is True:
            print()
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
        outmodule = join(outdir, 'drivers/staging/qcacld-3.0/wlan.ko')
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
            outmodule = join(outdir, 'drivers/staging/prima/wlan.ko')
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
        'name': name,
        'outdir': outdir,
        'outmodule': outmodule,
        'rundir': rundir,
        'scriptdir': scriptdir,
        'sourcedir': sourcedir,
        'tcdir': tcdir,
        'zipdir': zipdir,
        'zipname': zipname
    }


def toolchain():
    tcdir = variables()['tcdir']
    cc = parameters()['cc']
    gcc = join(tcdir, 'google-gcc/bin/aarch64-linux-android-')
    gcc32 = join(tcdir, 'google-gcc-32/bin/arm-linux-androideabi-')
    verbose = parameters()['verbose']
    if cc == 'clang':
        tcstrip = join(tcdir, 'google-clang/bin/llvm-strip')
    elif cc == 'gcc':
        tcstrip = join(tcdir, 'google-gcc/bin/aarch64-linux-android-strip')
    if cc == 'clang':
        clang = join(tcdir, 'google-clang/bin/clang')
        clangcc = ' '.join(['ccache', clang])
        clang_version = (f'$({clang} --version | head -n 1 | '
                         r'perl -pe "s/\(http.*?\)//gs" | '
                         'sed -e "s/  */ /g" -e "s/[[:space:]]*$//" | '
                         'cut -d " " -f-1,6-8)')
        # stdout=sys.stdout causing subprocess is giving NoneType output,
        # so we need special case for --verbose if it's True
        output = None
        if verbose is True:
            tmp = mkstemp()
            output = tmp[1]
            cmd = f'echo "{clang_version}" > {output}'
            subprocess_run(cmd)
            clang_version = open(f'{output}').read().strip('\n')
        else:
            cmd = f'echo "{clang_version}"'
            talk = subprocess_run(cmd)
            clang_version = talk[0].strip('\n')
        clangopt = ' '.join([f'CC="{clangcc}"',
                             'CLANG_TRIPLE="aarch64-linux-gnu-"',
                             'CLANG_TRIPLE_ARM32="arm-linux-gnueabi-"',
                            f'KBUILD_COMPILER_STRING="{clang_version}"'])
        if output is not None:
            remove(output)
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
    outdir = variables()['outdir']
    defconfig = variables()['defconfig']
    cc = parameters()['cc']
    gcc = toolchain()['gcc']
    gcc32 = toolchain()['gcc32']
    clangopt = toolchain()['clangopt']
    cmd = f'make ARCH=arm64 O="{outdir}" {defconfig}'
    subprocess_run(cmd)
    if cc == 'clang':
        cmd = (f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="{gcc}" '
               f'CROSS_COMPILE_ARM32="{gcc32}" -j4 {clangopt}')
    elif cc == 'gcc':
        cmd = (f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="ccache {gcc}'
               f'CROSS_COMPILE_ARM32="ccache {gcc32}" -j4')
    subprocess_run(cmd)


def make_wrapper():
    build_type = parameters()['type']
    oc = parameters()['overclock']
    device = parameters()['device']
    sourcedir = variables()['sourcedir']
    branch = variables()['branch']
    # In-Into sourcedir and change the branch
    chdir(sourcedir)
    cmd = f'git checkout {branch}'
    subprocess_run(cmd)
    if device == 'mido':
        if oc is False:
            revert_commit = {
                'custom': 'None',  # Haven't have time to rebase PIE
                'miui': '122cc6988b399885ea8918a790c01662a20e8463'
            }
            if build_type == 'miui':
                cmd = f'git revert --no-commit {revert_commit[build_type]}'
            elif build_type == 'custom':
                cmd = f'git revert --no-commit {revert_commit[build_type]}'
            subprocess_run(cmd)
    try:
        make()
    except CalledProcessError:
        if exists(join(sourcedir, '.config')
                  ) or exists(join(sourcedir, 'include/config')):
            # Just to make sure config is directory
            if isdir(join(sourcedir, 'include/config')):
                try:
                    print('cleaning...')
                    cmd = 'make -q mrproper'
                    subprocess_run(cmd)
                except CalledProcessError:
                    print('failed when cleaning, exiting...')
                    raise
                else:
                    print('re-runing the make again...')
                    make()
        else:
            print('failed to make kernel image...')
            return False
    else:
        print('Successfully built...')


def modules():
    build_type = parameters()['type']
    device = parameters()['device']
    moduledir = variables()['moduledir']
    outdir = variables()['outdir']
    outmodule = variables()['outmodules']
    srcdir = variables()['sourcedir']
    tcstrip = toolchain()['strip']
    if build_type == 'miui':
        if exists(outmodule) and isfile(outmodule):
            cmd = f'"{tcstrip}" --strip-unneeded "{outmodule}"'
            subprocess_run(cmd)
            if device == 'whyred':
                cmd = (f'"{outdir}/scripts/sign-file" sha512 '
                       f'"{outdir}/certs/signing_key.pem" '
                       f'"{outdir}/certs/signing_key.x509" '
                       f'"{outmodule}"')
            elif device == 'mido':
                cmd = (f'"{srcdir}/scripts/sign-file" sha512 '
                       f'"{outdir}/certs/signing_key.pem" '
                       f'"{outdir}/certs/signing_key.x509" '
                       f'"{outmodule}"')
            subprocess_run(cmd)
            if device == 'whyred':
                copy(outmodule, join(moduledir, 'qca_cld3/qca_cld3_wlan.ko'))
            elif device == 'mido':
                copy(outmodule, moduledir)
                copy(join(moduledir, 'wlan.ko'
                          ), join(moduledir, 'pronto/pronto_wlan.ko'))
        else:
            raise FileNotFoundError(f'{outmodule} not found...')


def zip_kernel():
    anykernel = variables()['anykernel']
    name = variables()['name']
    rundir = variables()['rundir']
    zipdir = variables()['zipdir']
    # TO-DO


def GoogleDriveUpload():
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle

    device = parameters()['device']
    zipname = variables()['zipname']
    scriptdir = variables()['scriptdir']
    finalzip = variables()['finalzip']

    folder_id = {
        'cpuquiet': '1i5XRVcO3Q8y8OFAOxXU-UWGWmQJiKo2u',
        'whyred': '1YjsSb1JYqWOANua07kd_UN4q2vPoq1iv',
        'mido': '1fkEmVBKD0cHMY1kbkpr4Bwm9v3COPPjf'
    }

    if device == 'whyred':
        folder_id = folder_id['whyred']
    elif device == 'mido':
        folder_id = folder_id['cpuquiet']

    file_metadata = {
        'name': zipname,
        'parents': [folder_id]
    }
    media = MediaFileUpload(finalzip,
                            mimetype='application/zip',
                            resumable=True)

    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.appdata',
        'https://www.googleapis.com/auth/drive.apps.readonly'
    ]

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
    file_zip = service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id').execute()
    file_id = file_zip.get('id')
    return file_id


def afh_upload():
    from ftplib import FTP, all_errors

    password = variables()['afh']
    finalzip = variables()['finalzip']
    with FTP('uploads.androidfilehost.com') as ftp:
        ftp.login('adek', password)
        try:
            ftp.storbinary(f'STOR {finalzip}', open(finalzip, 'rb'))
        except all_errors as e:
            raise e
        else:
            print('Upload success...')
            return True


def uploads():
    cpuquiet = parameters()['cpuquiet']
    finalzip = variables()['finalzip']
    if exists(finalzip) and isfile(finalzip):
        if cpuquiet is False:
            if afh_upload() is True:
                print('Creating mirror into GoogleDrive')
                GoogleDriveUpload()
        else:
            GoogleDriveUpload()


def main():
    if not exists('Makefile'):
        raise FileNotFoundError('Please run this script inside kernel tree')
    elif not isfile('Makefile'):
        raise IsADirectoryError('Makefile is a directory...')
