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
from threading import Thread
from os import remove, chdir
from os.path import exists, isfile, expanduser, join, realpath, isdir, dirname
from shutil import copy2 as copy
from tempfile import mkstemp
from time import time
start = time()
date_time = datetime.now().strftime('%Y%m%d-%H%M')


def parameters():
    param = ArgumentParser(description='Kernel Build Script.', )
    param.add_argument('-b', '--build',
                       choices=['miui', 'custom'], required=True)
    param.add_argument('-c', '--cpuquiet', action='store_true')
    param.add_argument('-d', '--device',
                       choices=['mido', 'whyred'], required=True)
    param.add_argument('-o', '--overclock',
                       action='store_true')
    param.add_argument('-r', '--release',
                       action='store_true')
    param.add_argument('-t', '--telegram',
                       action='store_true')
    param.add_argument('-u', '--upload',
                       action='store_true')
    param.add_argument('--verbose',
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
        if True in [cpuquiet, oc, build_type == 'custom']:
            param.error(
                '\n'
                '[-c/--cpuquiet, -o/--overclock, -b/--build = custom], '
                "isn't available for whyred"
            )
    elif device == 'mido':
        if cpuquiet is False:
            param.error('mido already drop support for non-cpuquiet')
    # Fail build if using version beta|test|personal while using --release
    if version in ['beta' or 'test' or 'personal'] and release is True:
        param.error(
            'version beta|test|personal, '
            "can't be passed with --release"
        )
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
        print(
            'An error was detected while running the subprocess:\n'
            f'exit code: {exitCode}\n'
            f'stdout: {talk[0]}\n'
            f'stderr: {talk[1]}'
        )
        raise CalledProcessError(exitCode, cmd)
    elif exitCode != 0 and verbose is True:
        # using sys.stdout/sys.stderr in Popen stdout/stderr
        # makes subproc.communicate() exit with NoneType status
        raise CalledProcessError(exitCode, cmd)
    return talk


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
    home = expanduser('~')
    rundir = os.getcwd()
    scriptdir = dirname(realpath(sys.argv[0]))
    kerneldir = join(home, 'kernel')
    sourcedir = join(kerneldir, device)
    anykernel = join(kerneldir, f'anykernel/{device}/{build_type}')
    outdir = join(kerneldir, f'build/out/target/kernel/{device}/{build_type}')
    zipdir = join(
        kerneldir,
        f'build/out/target/kernel/zip/{device}/{build_type}'
    )
    image = join(outdir, 'arch/arm64/boot/Image.gz-dtb')
    tcdir = join(kerneldir, 'toolchain')
    with open(f'{home}/keystore_password', 'r') as kp:
        keystore_password = kp.read().splitlines()[0].split('=')[1]
    with open(f'{home}/pass', 'r') as afh:
        afh_password = afh.read().splitlines()[0]
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
        clang_version = (
            f'$({clang} --version | head -n 1 | '
            r'perl -pe "s/\(http.*?\)//gs" | '
            'sed -e "s/  */ /g" -e "s/[[:space:]]*$//" | '
            'cut -d " " -f-1,6-8)'
        )
        # stdout=sys.stdout causing subprocess is giving NoneType output,
        # so we need special case for --verbose if it's True
        output = None
        if verbose is True:
            tmp = mkstemp()
            output = tmp[1]
            cmd = f'echo "{clang_version}" > {output}'
            subprocess_run(cmd)
            with open(f'{output}') as v:
                clang_version = v.read().strip('\n')
        else:
            cmd = f'echo "{clang_version}"'
            talk = subprocess_run(cmd)
            clang_version = talk[0].strip('\n')
        clangopt = ' '.join([
            f'CC="{clangcc}"',
            'CLANG_TRIPLE="aarch64-linux-gnu-"',
            'CLANG_TRIPLE_ARM32="arm-linux-gnueabi-"',
            f'KBUILD_COMPILER_STRING="{clang_version}"'
        ])
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
        cmd = (
            f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="{gcc}" '
            f'CROSS_COMPILE_ARM32="{gcc32}" -j4 {clangopt}'
        )
    elif cc == 'gcc':
        cmd = (
            f'make ARCH=arm64 O="{outdir}" CROSS_COMPILE="ccache {gcc}'
            f'CROSS_COMPILE_ARM32="ccache {gcc32}" -j4'
        )
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
        reset()
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
        if isfile(join(sourcedir, '.config')
                  ) or isdir(join(sourcedir, 'include/config')):
            try:
                print('=== cleaning... ===')
                cmd = 'make mrproper'
                subprocess_run(cmd)
            except CalledProcessError:
                print('!!! failed when cleaning, exiting... !!!')
                raise
            else:
                print('=== re-runing the make again... ===')
                make()
        else:
            reset()
            print('!!! failed to make kernel image... !!!')
            raise
    else:
        print()
        print('--- Successfully built... ---')
        print()
        reset()


def modules():
    cc = parameters()['cc']
    build_type = parameters()['type']
    device = parameters()['device']
    moduledir = variables()['moduledir']
    outdir = variables()['outdir']
    outmodule = variables()['outmodule']
    srcdir = variables()['sourcedir']
    tcstrip = toolchain()['strip']
    if build_type == 'miui':
        if isfile(outmodule):
            if cc == 'clang':
                cmd = f'"{tcstrip}" --strip-debug "{outmodule}"'
            elif cc == 'gcc':
                cmd = f'"{tcstrip}" --strip-unneeded "{outmodule}"'
            subprocess_run(cmd)
            if device == 'whyred':
                cmd = (f'"{outdir}/scripts/sign-file" sha512 '
                       f'"{outdir}/certs/signing_key.pem" '
                       f'"{outdir}/certs/signing_key.x509" '
                       f'"{outmodule}"')
            elif device == 'mido':
                cmd = (f'"{srcdir}/scripts/sign-file" sha512 '
                       f'"{outdir}/signing_key.priv" '
                       f'"{outdir}/signing_key.x509" '
                       f'"{outmodule}"')
            subprocess_run(cmd)
            if device == 'whyred':
                copy(outmodule, join(moduledir, 'qca_cld3/qca_cld3_wlan.ko'))
            elif device == 'mido':
                copy(outmodule, moduledir)
                copy(join(moduledir, 'wlan.ko'
                          ), join(moduledir, 'pronto/pronto_wlan.ko'))
        else:
            raise FileNotFoundError('!!! module not found... !!!')


def zip_now():
    from zipfile import ZipFile, ZIP_DEFLATED
    anykernel = variables()['anykernel']
    device = parameters()['device']
    image = variables()['image']
    finalzip = variables()['finalzip']
    moduledir = variables()['moduledir']
    release = parameters()['release']
    rundir = variables()['rundir']
    upload = parameters()['upload']
    version = parameters()['version']
    os.chdir(anykernel)
    if release is True and upload is True:
        with open('banner', 'w', newline='\n') as banner:
            banner.write('        ____       ____ ')
            banner.write('\n')
            banner.write('       / ___|     / ___|')
            banner.write('\n')
            banner.write(r'       \___ \    | |  _ ')
            banner.write('\n')
            banner.write(f'        ___) |{version}| |_| |')
            banner.write('\n')
            banner.write(r'       |____/torm \____|uard')
    # { delete old Image and Modules
    if isfile('Image.gz-dtb'):
        remove('Image.gz-dtb')
    if device == 'whyred':
        if isfile(join(moduledir, 'qca_cld3/qca_cld3_wlan.ko')):
            remove(join(moduledir, 'qca_cld3/qca_cld3_wlan.ko'))
    elif device == 'mido':
        if isfile(join(moduledir, 'qca_cld3/qca_cld3_wlan.ko')):
            remove(join(moduledir, 'pronto/pronto_wlan.ko'))
    # }
    if isfile(image):
        copy(image, anykernel)
    modules()
    zip_anykernel = ZipFile(finalzip, 'w', ZIP_DEFLATED)
    with zip_anykernel as ak:
        for root, directories, files in os.walk('.'):
            files = [f for f in files if not f[0] == '.']
            directories[:] = [d for d in directories if not d[0] == '.']
            for filename in files:
                ak.write(join(root, filename))
            # also write empty folder too
            for dirnames in directories:
                ak.write(join(root, dirnames))
    # Remove created banner
    remove('banner')
    os.chdir(rundir)
    finalzip_sign()


# haven't got some idea to sign via python directly without subprocess
def finalzip_sign():
    finalzip = variables()['finalzip']
    keystore_password = variables()['keystore']
    scriptdir = variables()['scriptdir']
    if isfile(finalzip):
        keystore = join(scriptdir, 'bin/stormguard.keystore')
        cmd = (
            f'echo "{keystore_password}" | '
            f'jarsigner -keystore {keystore} '
            f'"{finalzip}" stormguard'
        )
        subprocess_run(cmd)
    else:
        raise FileNotFoundError


def md5sum_zip(finalzip):
    import hashlib
    md5 = hashlib.md5()
    with open(finalzip, 'rb') as zip:
        while True:
            data = zip.read(4096)
            if not data:
                break
            md5.update(data)
    md5 = md5.hexdigest()
    return md5


def GoogleDrive_Creds():
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle
    scriptdir = variables()['scriptdir']
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.appdata',
        'https://www.googleapis.com/auth/drive.apps.readonly'
    ]
    creds = None
    if isfile(join(scriptdir, 'token.pickle')):
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


def GoogleDrive_checkFolder():
    service = GoogleDrive_Creds()
    device = parameters()['device']
    version = parameters()['version']
    print(' -> Checking folder...')
    parents_id = {
        'cpuquiet': '1i5XRVcO3Q8y8OFAOxXU-UWGWmQJiKo2u',
        'whyred': '1YjsSb1JYqWOANua07kd_UN4q2vPoq1iv',
        'mido': '1fkEmVBKD0cHMY1kbkpr4Bwm9v3COPPjf'
    }
    if device == 'whyred':
        parents_id = parents_id['whyred']
    elif device == 'mido':
        parents_id = parents_id['cpuquiet']
    folder_metadata = {
        'name': version,
        'parents': [parents_id],
        'mimeType': 'application/vnd.google-apps.folder'
    }
    page_token = None
    response = service.files().list(
        q=f"name='{version}'",
        spaces='drive',
        fields=(
            'nextPageToken, '
            'files(parents, name, id)'
        ),
        pageToken=page_token
    ).execute()
    try:
        is_exists = response.get('files', [])[0]
    except IndexError:
        print('    folder not exists, creating one...')
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        folder_id = folder.get('id')
    else:
        print('    folder exists, using it as parent...')
        name = is_exists.get('name')
        parent = is_exists.get('parents')[0]
        if name == version and parent == parents_id:
            folder_id = is_exists.get('id')
    page_token = response.get('nextPageToken', None)
    return folder_id


def GoogleDrive_Upload():
    from googleapiclient.http import MediaFileUpload
    finalzip = variables()['finalzip']
    folder_id = GoogleDrive_checkFolder()
    print(' -> Uploading to GoogleDrive...')
    service = GoogleDrive_Creds()
    zipname = variables()['zipname']
    file_metadata = {
        'name': zipname,
        'parents': [folder_id]
    }
    media = MediaFileUpload(
        finalzip,
        mimetype='application/zip',
        resumable=True
    )
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    file_id = file.get('id')
    return file_id


def afh_upload():
    from ftplib import FTP
    password = variables()['afh']
    finalzip = variables()['finalzip']
    zipname = variables()['zipname']
    with FTP('uploads.androidfilehost.com') as ftp:
        ftp.login('adek', password)
        try:
            ftp.storbinary(f'STOR {zipname}', open(finalzip, 'rb'))
        except Exception:
            ftp.delete(zipname)
            print('!!! deleting uploaded file... !!!')
            raise


def uploads():
    cpuquiet = parameters()['cpuquiet']
    finalzip = variables()['finalzip']
    home = variables()['home']
    release = parameters()['release']
    telegram = parameters()['telegram']
    verbose = parameters()['verbose']
    zipname = variables()['zipname']
    if isfile(finalzip):
        if cpuquiet is True:
            file_id = GoogleDrive_Upload()
            download_url = (
                'https://drive.google.com/'
                f'uc?id={file_id}&export=download'
            )
            if telegram is True:
                from requests import post
                md5 = md5sum_zip(finalzip)
                tg_chat = '-1001354431412'
                with open(f'{home}/token', 'r') as tg_token:
                    token = tg_token.read().splitlines()[0]
                tmp = mkstemp()
                msgtmp = tmp[1]
                with open(msgtmp, 'w', newline='\n') as msg:
                    msg.write('Build - Stormguard | CPUQuiet:')
                    msg.write('\n')
                    msg.write(f'[{zipname}]({download_url})')
                    msg.writelines('\n' + '\n')
                    msg.write(f'md5: `{md5}`')
                with open(msgtmp, 'r') as msg:
                    messages = (
                        ('chat_id', tg_chat),
                        ('text', msg.read()),
                        ('parse_mode', 'Markdown'),
                        ('disable_notification', 'no'),
                        ('disable_web_page_preview', 'yes')
                    )
                tg = 'https://api.telegram.org/bot' + token + '/sendMessage'
                telegram = post(tg, params=messages)
                if verbose is True:
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
        else:
            if release is True:
                afh_upload()
                print(' -> Creating mirror into GoogleDrive...')
                file_id = GoogleDrive_Upload()


def reset():
    device = parameters()['device']
    verbose = parameters()['verbose']
    if device == 'mido':
        if verbose is True:
            cmd = 'git reset -q --hard'
        else:
            cmd = 'git reset --hard'
        subprocess_run(cmd)
    else:
        return


def main():
    upload = parameters()['upload']
    if not exists('Makefile'):
        raise FileNotFoundError('Please run this script inside kernel tree')
    if not isfile('Makefile'):
        raise IsADirectoryError('Makefile is a directory...')
    parameters()
    P = Thread(target=make_wrapper)
    P.start()
    P.join()
    end = time()
    result = str(round((end - start) / 60, 2)).split('.')
    minutes = int(result[0])
    seconds = int(result[1])
    if seconds >= 60:
        minutes = minutes + 1
        seconds = seconds - 60
    if minutes <= 1:
        m_msg = 'minute'
        h = '==========================================='
    else:
        m_msg = 'minutes'
        h = '============================================'
    if seconds <= 1:
        s_msg = 'second'
    else:
        s_msg = 'seconds'
    print(h)
    print(f'--- build took {minutes} {m_msg}, and {seconds} {s_msg} ---')
    print(h)
    print()
    zip_now()
    if upload is True:
        print('==> Uploading...')
        uploads()
        print('==> Upload success...')


if __name__ == '__main__':
    main()
