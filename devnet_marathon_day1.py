#!/usr/bin/env python3
"""
# Домашняя работа. DevNetМарафон. День 1.

В качестве домашнего задания первого дня вам предлагается написать скриптдля решения задачи,
которая с виду покажется совсем простой, но вполне может забрать у вас достаточное количество душевных сил.
Рекомендуем внимательно прочитать задание.

Результат выполнения домашнего задания публикуйте ввашем репозитории на Github,
а ссылку на него –в чате с #ясделал.

Дано: сеть из нескольких коммутаторов и маршрутизаторов, все они доступны по своим IP-адресам.
Все IP-адреса устройств известны.Все коммутаторы и маршрутизаторы работаютпод управлением ОСIOSили IOS XE.

Необходимо:
1. Собрать со всех устройств файлы конфигураций, сохранить их на диск, используя имя устройства и текущую дату в составеимени файла.
2. Проверить на всех коммутаторах-включен ли протокол CDP и есть ли упроцесса CDPна каждом из устройств данные о соседях.
3. Проверить, какой типпрограммного обеспечения(NPEили PE)* используется на устройствах исобрать со всех устройств данные о версиииспользуемого ПО.
4. Настроить на всех устройствах timezone GMT+0, получение данных для синхронизациивремени от источника во внутренней сети, предварительно проверив его доступность.
5. Вывести отчет в виде нескольких строк, каждая изкоторых имеет следующийформат, близкий к такому:Имя устройства -тип устройства -версия ПО -NPE/PE -CDP on/off, Xpeers-NTP in sync/not sync.  
Необходимые пакеты:
python3 >=
pip3 install netmiko
"""
import sys
import os
import re
import datetime
import logging
import json
from multiprocessing import Process

from netmiko import ConnectHandler
from tabulate import tabulate

### аля константы
INVENTORY = 'inventory.json'
BACKUP_DIR = 'backups'
NTP_SERVER = '10.10.10.254'
TIMEZONE = 'GMT+0 0'
###

def main(ip, credentials):
    """
    ожидает: строку, словарь
    """
    logging.info('connection to device {}'.format(ip))
    device_params = {
        'device_type': credentials['device_type'],
        'ip': ip,
        'username': credentials['username'],
        'password': credentials['password'],
        'secret': credentials['secret']
    }

    with ConnectHandler(**device_params) as ssh:
        ssh.enable()


        ### сохранить конфиг ###
        result = ssh.send_command('show running-config')

        # проверить, создана ли папка для бекапов, если нет создать
        backup_dir = os.path.join(script_dir, BACKUP_DIR)
        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)
            logging.error("Directory [{}] created.".format(BACKUP_DIR))

        # дата и время
        date_time = datetime.datetime.now()
        date_time = datetime.datetime.strftime(date_time, '%d_%m_%YT%H_%M_%S')
        # date_time ~ '29_04_2020T01_31_55'

        filename = credentials['hostname'] + '_' + date_time
        with open(os.path.join(backup_dir, filename), 'w') as file:
            file.write(result)
        logging.info("Configuration from [{}] backed up in [{}]".format(
            credentials['hostname'], os.path.join(backup_dir, filename)
            )
        )

        output = []
        output.append(credentials['hostname'])

        ### модель
        result = ssh.send_command('show inventory')
        match = re.search(
            r'NAME:\s+"Chassis",\s+DESCR:\s+"((?:\S+\s?)+)"', result
            )
        if match:
            temp = match.groups()[0]
            output.append(temp)
        else:
            output.append('unknow')

        ### версия ПО
        result = ssh.send_command('show version')
        match = re.search(
            r'Version\s+(\S+),', result
            )
        if match:
            temp = match.groups()[0]
            output.append(temp)
        else:
            output.append('unknow')

        ### NPE/PE
        result = ssh.send_command('dir bootflash:/')
        if 'NPE' in result or 'npe' in result:
            output.append('NPE')
        elif 'PE' in result or 'pe' in result:
            output.append('PE')
        else:
            output.append('unknow')

        ### проверка CDP ###
        result = ssh.send_command('show cdp entry *')
        peers_count = len(re.findall(r'Device ID', result))
        if 'CDP is not enabled' in result:
            output.append('{}:: CDP is OFF, {} peers'.format(
                credentials['hostname'], str(peers_count)
                    )
                )
        else:
            output.append('{}:: CDP is ON, {} peers'.format(
                credentials['hostname'], str(peers_count)
                    )
                )

        ### timezone, ntp
        ssh.config_mode()
        ssh.send_command('clock timezone {}'.format(TIMEZONE))
        logging.info('{}:: Set [clock timezone {}]'.format(
            credentials['hostname'], TIMEZONE))
        ssh.send_command('ntp server {}'.format(NTP_SERVER))
        logging.info('{}:: Set [ntp server {}]'.format(
            credentials['hostname'], NTP_SERVER))
        ssh.exit_config_mode()
        # проверим доступность NTP-сервера
        result = ssh.send_command('ping {}'.format(NTP_SERVER))
        if ('Success rate is 0' in result or
            '0 packets received' in result):
            output.append('Clock is not Sync')
            logging.info('{}:: NTP-server: [{}] unavailable.'.format(
                credentials['hostname'], NTP_SERVER))
        else:
            output.append('Clock is Sync')
            logging.info('{}:: NTP-server: [{}] available.'.format(
                credentials['hostname'], NTP_SERVER))

        with open('output.txt', 'a') as file:
            file.write(';'.join(output) + '\n')
        ssh.disconnect()

        ### проверка NPEили PE ###
if __name__ == "__main__":
    # полный путь до папки запускаемого скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # включить логирование в stdout и в файл devnet_marathon_day1.log рядом
    # со скриптом
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | PID: %(process)d | %(levelname)s~: %(message)s',
        handlers=[
            logging.FileHandler(
                "{}".format(os.path.join(
                    script_dir, "devnet_marathon_day1.log")
                    ),
                mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # загрузить inventory.json
    if not os.path.exists(os.path.join(script_dir, INVENTORY)):
        logging.error("Can't find {}.".format(INVENTORY))
        sys.exit()
    with open(os.path.join(script_dir, INVENTORY), 'r') as file:
        inventory = json.load(file)

    # распаралелить функцию main
    try:
        for ip in inventory:
            procs = []
            proc = Process(target=main, args=(ip,inventory[ip]))
            procs.append(proc)
            proc.start()
            logging.info('Working on - [{}]'.format(ip))
        for proc in procs:
            proc.join()
        logging.info('All devices in {} processed.'.format(INVENTORY))

        with open('output.txt') as file:
            output = file.readlines()
        os.remove('output.txt')
        output.sort()
        final_result = []         
        for i in output:
            i = i.strip().split(';') 
            final_result.append(i)
        columns = ['Hostname', 'Device type', 'F/W Version', 'NPE/PE status',
            'CDP status', 'CLOCK status']
        print(tabulate(final_result, headers=columns))
    except KeyboardInterrupt:
        for proc in procs:
            proc.terminate()
        logging.warning('Script stopped by user.')
        sys.exit()
