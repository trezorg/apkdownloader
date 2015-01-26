#!/usr/bin/env python
from __future__ import print_function
import logging
import codecs
import yaml
import os
import sys
import argparse
from colorama import init as colorama_init, Fore
from clint.textui import progress
if __package__ is None:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from apkdownloader import (
    create_db,
    get_access_token,
    get_apks_records,
    delete_apks_records,
    update_access_token,
    update_apk_info,
    GooglePlayAPI,
    ApkInfo,
)

logging.basicConfig()
logger = logging.getLogger('apkdownloader')
logger.setLevel(logging.INFO)

DOWNLOAD_CHUNK_SIZE = 1024
DEFAULT_CONFIG_FILENAME = "apk.yml"
DEFAULT_CONFIGS = [
    os.path.expanduser("~/{}".format(DEFAULT_CONFIG_FILENAME)),
    os.path.join(os.path.curdir, DEFAULT_CONFIG_FILENAME)
]
DESCRIPTION_TEXT = """
    Set mandatory arguments email, password, adroid_id either in a config file
    or in the command line. The config file can be set in the command line
    using the argument --config. Also the file {0} will be seek in
    the current directory and in the home directory of the current user.
    In the case of many config files are being found they will be meld in the
    next order (home directory, current directory, command line argument).
    Example of config file: apk_config.yml
""".format(DEFAULT_CONFIG_FILENAME)


def sizeof_fmt(num, suffix='B'):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "{0:.1f}{1}{2}".format(num, unit, suffix)
        num /= 1024.0
    return "{0:.1f}{1}{2}".format(num, 'Yi', suffix)


def _print_color_line(text, color):
    message = '{}{}{}'.format(color, text, Fore.RESET)
    print(message)


def filter_config_files(*args):
    for filename in args:
        if filename and os.path.isfile(filename):
            yield filename


def read_config(filename):
    try:
        fln = codecs.open(filename, encoding="utf-8")
        return yaml.load(fln.read())
    except Exception as err:
        logger.error(err)
        return {}


def meld_configs(result, *options):
    result = result or {}
    for option in options:
        option = {k: v for k, v in option.items() if v}
        for key, value in option.items():
            if isinstance(value, (list, tuple)):
                values = result.get(key, [])
                values.extend(value)
                result[key] = list(set((values)))
            elif isinstance(value, dict):
                values = result.get(key, {})
                values.update(value)
                result[key] = values
            else:
                result[key] = value
    return result


def read_configs(*args):
    result = {}
    for filename in args:
        config = read_config(filename)
        result = meld_configs(result, config)
    return result


def check_absent_options(options, names):
    return [name for name in names if not options.get(name)]


def check_options(options):
    absent_options = check_absent_options(options, [
        "android_id",
        "email",
        "password",
        "db",
        "directory",
        "apks",
    ])
    if absent_options:
        _print_color_line(
            "Absent parameters: {}.\nYou should set them either in the"
            " config file or in the command line.\n".format(absent_options),
            Fore.RED)
        return False
    return True


def check_directory(directory):
    if not os.path.isdir(directory):
        raise argparse.ArgumentTypeError(
            'Directory is not exists: %s' % directory)
    return directory


def check_config(filename):
    if not os.path.isfile(filename):
        raise argparse.ArgumentTypeError(
            'Filename is not exists: %s' % filename)
    return filename


def get_packages_info(api, apks):
    apks_info = {}
    for name in apks:
        apk_details = api.details(name)
        doc = apk_details.docV2
        version_code = doc.details.appDetails.versionCode
        version_string = doc.details.appDetails.versionString
        offer_type = doc.offer[0].offerType
        apk_size = doc.details.appDetails.installationSize
        apks_info[name] = ApkInfo(
            name, version_code, version_string, offer_type, apk_size)
    return apks_info


def show_packages_info(new_apks_info, current_apks):
    _print_color_line(
        "{0:<50}{1:<20}{2:<20}{3}".format(
            'name', 'code', 'version', 'size'), Fore.RED)
    if new_apks_info:
        _print_color_line("Updated packages:", Fore.GREEN)
        for name in sorted(new_apks_info.keys()):
            apk_info = new_apks_info[name]
            _print_color_line(
                "{0.name:<50}{0.code:<20}{0.version:<20}{1}".
                format(apk_info, sizeof_fmt(apk_info.size)), Fore.GREEN)
    old_apks_keys = sorted(
        (set(current_apks.keys()) - set(new_apks_info.keys())))
    if old_apks_keys:
        _print_color_line("Current packages:", Fore.RED)
        for name in old_apks_keys:
            apk_info = current_apks[name]
            _print_color_line(
                "{0.name:<50}{0.code:<20}{0.version:<20}{1}".
                format(apk_info, sizeof_fmt(apk_info.size)), Fore.YELLOW)


def download_packages(api, packages_info, options):
    db = options["db"]
    dry_run = options["dry_run"]
    directory = options["directory"]
    apks_directory = os.path.abspath(directory)
    for name in sorted(packages_info.keys()):
        info = packages_info[name]
        _print_color_line(
            "Apk file {0} should be updated to version {1}".
            format(name, info.version), Fore.RED)
        if not dry_run:
            _print_color_line(
                "Downloading apk {0} with size {1}...".
                format(name, sizeof_fmt(info.size)), Fore.GREEN)
            stream = api.download(name, info.code, info.offer, stream=True)
            filename = os.path.join(
                apks_directory, "{0}.{1}.apk".format(name, info.version))
            with open(filename, 'wb') as f:
                total_length = int(stream.headers.get('content-length'))
                expected_size = total_length / DOWNLOAD_CHUNK_SIZE + 1
                for chunk in progress.bar(
                        stream.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE),
                        expected_size=expected_size):
                    if chunk:
                        f.write(chunk)
                        f.flush()
        update_apk_info(db, info)


def prepare_parser():
    """
    Handle the command line arguments
    """
    parser = argparse.ArgumentParser(
        prog="apk",
        description="\n".join(
            [s.lstrip() for s in DESCRIPTION_TEXT.splitlines()]),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        "-i",
        "--android_id",
        required=False,
        action="store",
        dest="android_id",
        type=str,
        help="Android ID")

    parser.add_argument(
        "-e",
        "--email",
        required=False,
        action="store",
        dest="email",
        type=str,
        help="Google play email")

    parser.add_argument(
        "-p",
        "--password",
        required=False,
        action="store",
        dest="password",
        type=str,
        help="Google play password")

    parser.add_argument(
        "-b",
        "--db",
        required=False,
        action="store",
        dest="db",
        type=str,
        help="Database file")

    parser.add_argument(
        "-d",
        "--directory",
        required=False,
        action="store",
        dest="directory",
        type=check_directory,
        help="Directory to save files")

    parser.add_argument(
        "-c",
        "--config",
        required=False,
        action="store",
        dest="config",
        type=check_config,
        help="Config file")

    parser.add_argument(
        "-a",
        "--apks",
        required=False,
        action="store",
        nargs='+',
        dest="apks",
        type=str,
        help="Apks to download")

    parser.add_argument(
        "-f",
        "--force",
        required=False,
        action="store_true",
        dest="force",
        default=False,
        help="Force download apks")

    parser.add_argument(
        "-r",
        "--recreate",
        required=False,
        action="store_true",
        dest="recreate",
        default=False,
        help="Re-create apks info database")

    parser.add_argument(
        "--dry-run",
        required=False,
        action="store_true",
        dest="dry_run",
        default=False,
        help="Do not download apk packages")

    parser.add_argument(
        "-s",
        "--info",
        required=False,
        action="store_true",
        dest="info",
        default=False,
        help="Show info about packages")

    return parser


def main():
    parser = prepare_parser()
    args_options = {
        k: v for k, v in vars(parser.parse_args()).items() if v is not None
    }
    allowed_configs = DEFAULT_CONFIGS + [args_options.get("config")]
    config_files = list(filter_config_files(*allowed_configs))
    options = read_configs(*config_files)
    options.update(args_options)
    if not check_options(options):
        parser.print_help()
        return
    if not os.path.isdir(options["directory"]):
        logger.error("Direcory {} is not exists.".format(options["directory"]))
        parser.print_help()
        return
    db = options["db"]
    force = options["force"]
    recreate = options["recreate"]
    create_db(db, recreate)
    access_token = get_access_token(db)
    current_apks = get_apks_records(db)
    apks = options["apks"]
    outdated_packages = set(current_apks) - set(apks)
    if outdated_packages:
        delete_apks_records(db, tuple(outdated_packages))
        current_apks = get_apks_records(db)
    params = {
        "androidId": options["android_id"],
        "email": options["email"],
        "password": options["password"],
        "auth_sub_token": access_token,
        "debug": True
    }
    api = GooglePlayAPI(**params)
    apks_details = api.bulkDetails(apks)
    update_access_token(db, api.get_token())
    apks_data = {
        name: m.doc.details.appDetails.versionCode
        for name, m in zip(apks, apks_details.entry)
    }
    new_apks = [
        name
        for name, ver in apks_data.items()
        if force or (name not in current_apks or current_apks[name].code < ver)
    ]
    colorama_init()
    new_apks_info = get_packages_info(api, new_apks)
    if options["info"]:
        show_packages_info(new_apks_info, current_apks)
        return
    if not new_apks_info:
        _print_color_line("There are no new apk packages to update", Fore.RED)
        return
    download_packages(api, new_apks_info, options)


if __name__ == "__main__":
    if __package__ is None:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    main()
