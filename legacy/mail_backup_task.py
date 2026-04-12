import os
import sys
from webdav3.client import Client
import datetime
import shutil

def set_params_from_env():
    print("Установка параметров из env файла")
    try:
        return {
            'hostname_webdav_nextcloud': 'https://webdav.cloud.mail.ru',
            'webdav_usr': os.getenv('CLOUD_USER'),
            'webdav_password': os.getenv('CLOUD_PASS'),
            'base_list': os.getenv('BACKUP_BASE_LIST').split(','),
            'main_folder': os.getenv('CLOUD_MAIN_BACKUP_FOLDER'),
            'db_folder': os.getenv('CLOUD_DB_BACKUP_FOLDER'),
            'src_folder': os.getenv('CLOUD_SRC_BACKUP_FOLDER'),
            'local_db_path': os.getenv('BACKUP_DB_LOCALPATH'),
            'local_src_path': os.getenv('BACKUP_SRC_LOCALPATH'),
            'time_format': os.getenv('CLOUD_BACKUP_TIMEFORMAT'),
            'compress_db_type': os.getenv('CLOUD_BACKUP_DB_COMPRESSION'),
            'compress_src_type': os.getenv('CLOUD_BACKUP_SRC_COMPRESSION'),
            'bckp_items_limit': int(os.getenv('CLOUD_BACKUP_LIMIT')),
            'archive_items_limit': int(os.getenv('CLOUD_ARCHIVE_LIMIT')),
            'create_src_archive': int(os.getenv('CREATE_SRC_ARCHIVE'))
        }
    except Exception as e:
        print(str(e))
        print("Error: Ошибка в процессе установки переменных из env файла")
        sys.exit()


def webdav_con(webdav_hostname, webdav_usr, webdav_password):
    print("Установка соединения с облачным хранилищем")
    options = {
        'webdav_hostname': webdav_hostname,
        'webdav_login':webdav_usr,
        'webdav_password': webdav_password,
    }
    try:
        client = Client(options)
        return client
    except Exception as e:
        print(str(e))
        print("Error: Ошибка в процессе создания соединения с облачным хранилищем")
        sys.exit()


def create_folder_structure(client, prms):
    print("Проверка и создание требуемой файловой структуры в облачном хранилище")
    try:
        if not client.check(prms['main_folder']):
            client.mkdir(prms['main_folder'])

        if not client.check(prms['main_folder'] + "/" + prms['db_folder']):
            client.mkdir(prms['main_folder'] + "/" + prms['db_folder'])

        if not client.check(prms['main_folder'] + "/" + prms['src_folder']):
            client.mkdir(prms['main_folder'] + "/" + prms['src_folder'])

    except Exception as e:
        print(str(e))
        print("Error: Ошибка в процессе проверки и создания файловой структуры в облачным хранилищем")
        sys.exit()

def delete_unrecognize_local_files(filename, target, prms):
    if target == 'db':
        try:
            os.remove(prms['local_db_path'] + filename)
        except Exception as e:
            print(str(e))
            print("Warn: нельзя удалить файл -> ", prms['local_db_path'] + filename)

    elif target == 'src':
        try:
            os.remove(prms['local_src_path'] + filename)
        except Exception as e:
            print(str(e))
            print("Warn: нельзя удалить файл -> ", prms['local_src_path'] + filename)

def delete_files(files_dict, prms, target, client=None):
    if target == 'db':
        print("Удаление устаревших бэкап-файлов и возвращение списка оставшихся файлов")

        try:
            remains_files = []
            for item in files_dict:
                base_files_list = files_dict[item]
                # print("base_files_list: ", base_files_list)
                files_to_delete = base_files_list[prms['bckp_items_limit']:]
                if len(files_to_delete) > 0:
                    for del_item in files_to_delete:
                        # print("del_item: ", del_item)
                        if client is not None:
                            try:
                                client.clean(prms['main_folder'] + "/" + prms['db_folder'] + '/' + del_item['filename'])
                            except:
                                print ("Warn: невозможно удалить файл -> ", prms['main_folder'] + "/" + prms['db_folder'] + '/' + del_item['filename'])
                        else:
                            os.remove(prms['local_db_path'] + del_item['filename'])
                for rem_item in base_files_list[:prms['bckp_items_limit']]:
                    remains_files.append(rem_item['filename'])

            return remains_files
        except Exception as e:
            print(str(e))
            print("Error: Ошибка в процессе удаления устаревших бэкап-файлов")
            sys.exit()

    elif target == 'src':
        try:
            remains_files = []

            base_files_list = files_dict['src']

            files_to_delete = base_files_list[prms['archive_items_limit']:]

            if len(files_to_delete) > 0:
                for del_item in files_to_delete:
                    # print("del_item: ", del_item)
                    if client is not None:
                        try:
                            client.clean(prms['main_folder'] + "/" + prms['src_folder'] + '/' + del_item['filename'])
                        except:
                            print ("Warn: невозможно удалить файл -> ", prms['main_folder'] + "/" + prms['src_folder'] + '/' + del_item['filename'])
                    else:
                        os.remove(prms['local_src_path'] + del_item['filename'])

            for rem_item in base_files_list[:prms['archive_items_limit']]:
                remains_files.append(rem_item['filename'])

            return remains_files
        except Exception as e:
            print(str(e))
            print("Error: Ошибка в процессе удаления устаревших бэкап-файлов")
            sys.exit()
    else:
        print("Error: Не задан параметр target для delete_files")
        sys.exit()

def create_files_dict(listdir, prms, target):

    if target == 'db':
        print("Создание словаря с перечнем бэкап-файлов и разбивкой по конкретным базам")

        try:
            files_dict = {}

            for backup_item in listdir:
                if backup_item.split('.')[-1] == prms['compress_db_type']:
                    base_name = backup_item.split('_')[1]
                    if base_name in prms['base_list']:
                        backup_date = datetime.datetime.strptime(backup_item.split('_')[3].split('.')[0],
                                                                 prms['time_format'])
                        if base_name not in files_dict:
                            files_dict[base_name] = []
                        files_dict[base_name].append({'filename': backup_item, 'date': backup_date})
                else:
                    delete_unrecognize_local_files(backup_item, target, prms)

            for dict_item in files_dict:
                sorted_list = sorted(files_dict[dict_item], key=lambda x: x['date'], reverse=True)
                files_dict[dict_item] = sorted_list

            return files_dict

        except Exception as e:
            print(str(e))
            print("Error: Ошибка в процессе cоздание словаря с перечнем бэкап-файлов")
            sys.exit()

    elif target == 'src':
        files_dict = {
            'src': []
        }

        for backup_item in listdir:
            if backup_item.split('.')[-1] == prms['compress_src_type']:
                backup_date = datetime.datetime.strptime(backup_item.split('_')[1].split('.')[0],
                                                             prms['time_format'])
                files_dict['src'].append({'filename': backup_item, 'date': backup_date})
            else:
                delete_unrecognize_local_files(backup_item, target, prms)

        sorted_list = sorted(files_dict['src'], key=lambda x: x['date'], reverse=True)

        files_dict['src'] = sorted_list
        return files_dict

    else:
        print("Error: Не задан параметр target для create_files_dict")
        sys.exit()

def service_local_files(prms, target):
    print("Старт общей сервисной функции для работы с локальными файлами")
    print("target: ", target)
    if target == 'db':
        local_files = os.listdir(prms['local_db_path'])
        # print("local_files: ", local_files)
        local_files_dict = create_files_dict(local_files, prms, 'db')
        # print("local_files_dict: ", local_files_dict)
        remains_files = delete_files(local_files_dict, prms, 'db')
        # print("remains_files: ", remains_files)
        return remains_files

    elif target == 'src':

        if prms['create_src_archive'] == 1:
            archive_name = "vekolomsrc_" + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            print(prms['local_src_path'] + archive_name)
            shutil.make_archive(prms['local_src_path'] + archive_name, 'zip', '/usr/src/vekolom')

        local_files = os.listdir(prms['local_src_path'])
        # print("local_files: ", local_files)
        local_files_dict = create_files_dict(local_files, prms, 'src')
        # print("local_files_dict: ", local_files_dict)

        remains_files = delete_files(local_files_dict, prms, 'src')
        # print("remains_files: ", remains_files)
        return remains_files
    else:
        print("Error: Не задан параметр target для service_local_files")
        sys.exit()

def delete_unrecognize_cloud_files(client, raw_item, target, prms):
    if not raw_item['isdir']:

        filename = raw_item['path'].split('/')[-1]

        if target == 'db':
            try:
                client.clean(prms['main_folder'] + "/" + prms['db_folder'] + '/' + filename)
            except Exception as e:
                print(str(e))
                print("Warn: нельзя удалить файл -> ", prms['main_folder'] + "/" + prms['db_folder'] + '/' + filename)

        elif target == 'src':

            try:
                client.clean(prms['main_folder'] + "/" + prms['src_folder'] + '/' + filename)
            except Exception as e:
                print("Warn: нельзя удалить файл -> ", prms['main_folder'] + "/" + prms['db_folder'] + '/' + filename)

def get_cloudfiles_list(listdir, prms, target, client=None):
    print("Формирования списка файлов в заданной директории облачного хранилища")

    try:
        cloud_files = []

        if target == 'db':
            comp_type = prms['compress_db_type']
        elif target == 'src':
            comp_type = prms['compress_src_type']
        else:
            print("Error: Не задан параметр target для get_cloudfiles_list")
            sys.exit()

        for raw_item in listdir:
            if not raw_item['isdir'] and raw_item['path'].split('\/')[-1].split('.')[-1] == comp_type:
                filename = raw_item['path'].split('/')[-1]
                if target == 'db':
                    base_name = filename.split('_')[1]
                    if base_name in prms['base_list']:
                        cloud_files.append(filename)
                else:
                    cloud_files.append(filename)
            else:
                delete_unrecognize_cloud_files(client, raw_item, target, prms)

        return cloud_files
    except Exception as e:
        print(str(e))
        print("Error: Ошибка в процессе формирования списка файлов в заданной директории облачного хранилища")
        sys.exit()

def service_cloud_files(client, remains_local_files, target, prms):
    print("Старт общей сервисной функции для работы с облачными файлами")

    if target == 'db':
        listdir = client.list(prms['main_folder'] + "/" + prms['db_folder'], get_info=True)

        cloud_files = get_cloudfiles_list(listdir, prms, 'db', client)

        # print("cloud_files: ", cloud_files)

        for rem_item in remains_local_files:
            if rem_item not in cloud_files:
                client.upload_sync(remote_path=prms['main_folder'] + "/" + prms['db_folder'] + "/" + rem_item,
                                   local_path=prms['local_db_path'] + rem_item)

        listdir = client.list(prms['main_folder'] + "/" + prms['db_folder'], get_info=True)
        cloud_files = get_cloudfiles_list(listdir, prms, 'db', client)
        # print("cloud_files: ", cloud_files)
        cloud_files_dict = create_files_dict(cloud_files, prms, 'db')
        # print("cloud_files_dict: ", cloud_files_dict)
        delete_files(cloud_files_dict, prms, 'db', client)

    elif target == 'src':
        listdir = client.list(prms['main_folder'] + "/" + prms['src_folder'], get_info=True)
        cloud_files = get_cloudfiles_list(listdir, prms, 'src', client)
        # print("cloud_files: ", cloud_files)
        for rem_item in remains_local_files:
            if rem_item not in cloud_files:
                client.upload_sync(remote_path=prms['main_folder'] + "/" + prms['src_folder'] + "/" + rem_item,
                                   local_path=prms['local_src_path'] + rem_item)
        listdir = client.list(prms['main_folder'] + "/" + prms['src_folder'], get_info=True)
        cloud_files = get_cloudfiles_list(listdir, prms, 'src', client)
        # print("cloud_files: ", cloud_files)
        cloud_files_dict = create_files_dict(cloud_files, prms, 'src')
        # print("cloud_files_dict: ", cloud_files_dict)
        delete_files(cloud_files_dict, prms, 'src', client)
    else:
        print("Error: Не задан параметр target для service_cloud_files")
        sys.exit()


def main():
    print("Начало работы: ", datetime.datetime.now().strftime("%d-%m-%Y %H:%M"))
    prms = set_params_from_env()
    # print("Параметры работы скрипта: ", prms)
    cloud_client = webdav_con(prms['hostname_webdav_nextcloud'], prms['webdav_usr'], prms['webdav_password'])
    print(cloud_client)
    create_folder_structure(cloud_client, prms)
    remains_local_archive_files = service_local_files(prms, 'src')
    service_cloud_files(cloud_client, remains_local_archive_files, 'src', prms)
    remains_local_files = service_local_files(prms, 'db')
    service_cloud_files(cloud_client, remains_local_files, 'db', prms)
    print("Завершение работы: ", datetime.datetime.now().strftime("%d-%m-%Y %H:%M"))

if __name__ == "__main__":
    main()