#!/usr/bin/env python
# -*- coding: utf-8 -*-

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';
import os
import sys
import re
import logging
import gzip
import configparser
from string import Template
from typing import Optional, Tuple, List, Dict, Callable

CONFIG_DEFAULT = {'config_filename': 'settings.ini',
                  'logging_path': '',
                  'log_dir': './logs',
                  'pattern_logs_filename': r'nginx-access-ui.log-\d{8}(.gz)*$',
                  'report_template_filename': 'report.html',
                  'report_template_dir': './',
                  'report_dir': 'reports',
                  'report_size': '1000',
                  'parsing_error': '50.0'}


def get_config_filename(config: Dict) -> Optional[str]:
    """ возвращает имя конфиг файла по умолчанию """
    if config and 'config_filename' in config:
        return config['config_filename']
    return None


def get_config_filename_from_cmd(cmd_args: Optional[List[str]]) -> Optional[str]:
    """ возвращает имя конфиг файла из коммандной строки: --config <filename> """
    config_filename_from_cmd = None
    if cmd_args and ('--config' in cmd_args) and (cmd_args.index('--config') < len(cmd_args)-1):
        config_filename_from_cmd = cmd_args[cmd_args.index('--config')+1]
    return config_filename_from_cmd


def get_config(config_def: Dict, cmd_args: List[str] = None) -> Optional[Dict]:
    """ возвращает конфиг-словарь, с учетом параметров в конфиг файле и значений по умолчанию """
    #print(config_def, cmd_args)
    config_filename = get_config_filename(config_def)
    config_filename_from_cmd = get_config_filename_from_cmd(cmd_args)
    config_filename = config_filename_from_cmd or config_filename
    if not config_def or not config_filename:
        logging.error('Bad config filename')
        return None
    cfg = configparser.ConfigParser()
    try:
        cfg['DEFAULT'] = dict(config_def)
    except Exception:
        logging.exception('Bad CONFIG_DEFAULT')
        return None
    if os.path.exists(config_filename) and os.path.isfile(config_filename):
        try:
            cfg.read(config_filename)
        except Exception:
            logging.exception('Error load settings from ini file')
            return None
        result = dict(cfg['DEFAULT'])
        try:
            float(result['parsing_error'])
            int(result['report_size'])
        except Exception:
            logging.exception('Bad config parameters: parsing_error, report_size')
            return None
        return result
    logging.error('Ini file not found')
    return None


def init_logging(logging_output: str = None) -> bool:
    """ устанавливает формат записи в журнал логов программы
    :param logging_output: имя файла/потока для вывода журнала логов, при None - вывод в stdout
    :return: True - если все успешно, False - в случае ошибки
    """
    try:
        logging.basicConfig(filename=str(logging_output),
                            filemode='a',
                            format='[%(asctime)s] %(levelname).1s %(message)s',
                            datefmt='%Y.%m.%d %H:%M:%S',
                            level=logging.INFO)
    except Exception:
        logging.exception('Error initializing the logging system')
        return False
    logging.info('Start.')
    return True


def get_last_logs_filename(logs_dir: str, pattern_log_filename: str) -> Optional[str]:
    """ возвращает имя последнего файла с логами NGINX
    :param logs_dir: каталог с логами
    :param pattern_log_filename: шаблон имени файла с логами
    :return: имя последнего файла с логами
             или None - в случае ошибок
    """
    if not logs_dir or not os.path.isdir(logs_dir):
        logging.error('LOGs directory not found. LOG_DIR: %s' % logs_dir)
        return None
    last_filename = None
    try:
        listdir = os.listdir(logs_dir)
    except Exception:
        logging.exception('LOGs directory don`t open. LOG_DIR: "%s"' % logs_dir)
        return None
    for file in listdir:
        if re.match(pattern_log_filename, file):
            if not last_filename or (re.findall(r'\d{8}', file) > re.findall(r'\d{8}', last_filename)):
                last_filename = file
    if not last_filename:
        logging.info('LOGS files not found in directory')
        return None
    return last_filename


def get_report_filename(log_filename: str) -> Optional[str]:
    """ возвращает имя файла HTML отчёта в соответствии с именем файла с логами
    :param log_filename: имя файла с логами NGINX
    :return: имя файла с HTML отчётом или None - в случае ошибок
    """
    date = re.search(r'\d{8}', log_filename)
    if not date:
        return None
    date_str = date.group()
    filename = '%s-%s.%s.%s.html' % ('report', date_str[0:4], date_str[4:6], date_str[6:8])
    return filename


def check_exist_reports_directory(report_dir: str) -> bool:
    """ Проверяет наличие каталога с HTML отчетами
    :param report_dir: каталог с отчетами
    :return: True - каталог имеется или False - в случае ошибок
    """
    if report_dir and os.path.exists(report_dir):
        if os.path.isdir(report_dir):
            return True
    logging.error('Error HTML report directory. "%s"' % report_dir)
    return False


def check_exist_report_file(directory: str, filename: str) -> bool:
    """ Проверяет наличие файл HTML отчета
    :param directory: каталог с отчетами
    :param filename: имя файла c HTML отчетом
    :return: True или False - в случае ошибок
    """
    if filename:
        report_path = os.path.join(directory, filename)
        if report_path and os.path.exists(report_path) and os.path.isfile(report_path):
            return True
    return False


def get_median_value_from_list(list_values: List[float]) -> Optional[float]:
    """ Возвращает медианное значение списка """
    if not (len(list_values) > 0):
        return None
    sorted_list = sorted(list(list_values))
    length = len(sorted_list)
    center = length // 2
    if length == 1:
        return sorted_list[0]
    elif length % 2 == 0:
        return sum(sorted_list[center-1:center+1]) / 2
    else:
        return sorted_list[center]


def parser_log_string(log_string: str) -> Optional[Tuple]:
    """ Парсит строку лога NGINX и возвращает кортеж значений (<URL>, <time_request>)
    192.168.122.1 - - [20/Feb/2012:14:56:26 +0000] "GET /index.html HTTP/1.1" 304 0 "-" "http_user_agent" "-" 39.023
    :param log_string: строка лог файла
    :return: tuple(url, request_time)
    """
    pattern_list = list()
    pattern_list.append(r'"(([^"]+)(\s+)([^"]+)(\s+)([^"]+))"')  # get ["GET /index.html HTTP/1.1"] from log_string
    pattern_list.append(r'\d+.\d+$')                             # get ["39.023] from log_string
    generator_pattern = [re.compile(i) for i in pattern_list]
    list_result = [n.search(log_string) for n in generator_pattern]
    if list_result[0] is not None and list_result[1] is not None:
        url = list_result[0].group().split(' ')[1]
        time_request = list_result[1].group()
        result = url, time_request
        return result
    return None


def get_func_open_file_by_extension(filename: str) -> Callable:
    """" в зависимости от расширения файла возвращает функцию для открытия файла
    gz - gzip.open, else open """
    if re.search(r"[.]gz$", filename):
        return gzip.open
    else:
        return open


def get_statistics_logs(log_dir: str, log_filename: str) -> Optional[Tuple[List[Dict], float]]:
    """ читает и анализирует файл логов NGINX и возвращает данные по найденным URL и процент ошибок
    :param log_dir: - каталог с логами NGINX
    :param log_filename: - имя файла с логами NGINX
    :return tuple(list(dict), error_rate) или False - в случае ошибок
    """
    if not log_filename:
        return None
    log_path = os.path.join(log_dir, log_filename)
    func_openfile = get_func_open_file_by_extension(log_path)
    try:
        file = func_openfile(log_path, 'rt', encoding='UTF-8')
    except Exception:
        logging.exception('Log file open error %s' % log_path)
        return None
    count_error_string = 0                  # count of error string in LOG file
    count_log_string = 0                    # count string in LOG file
    time_sum = 0.0                          # sum of time_request in all URL
    urls_time_request: Dict = {}      # словарь key=URL, value=list(time_request)
    # создаем генератор для построчного анализа лог файла на выходе tuple(<url>, <time_request>)
    list_res = map(parser_log_string, (line.rstrip() for line in file))
    # формируем словарь {<url>: list(<time_request>)}
    for res in list_res:                    # проходим по строкам файла с логами
        count_log_string += 1               # считаем общее кол-во строк в лог файле
        if not res:                         # битые строки в логе пропускаем
            count_error_string += 1         # считаем битые строки
            continue
        url = res[0]                        # URL - res[0]
        time_request = float(res[1])        # TIME_REQUEST - res[1]
        if not urls_time_request.get(url):  # новый URL - > добавляем новый ключ
            urls_time_request[url] = []
        urls_time_request[url].append(time_request)     # добавляем в список time_request
        time_sum += time_request
    file.close()
    result = []
    count_sum = count_log_string - count_error_string
    # считаем статистику по URL -> list({'url': <url>, 'count': <url_count> ...})
    for key, value in urls_time_request.items():
        url_stat = dict()
        url_stat['url'] = key
        url_stat['count'] = len(value)
        url_stat['count_perc'] = url_stat['count'] * 100 / count_sum
        url_stat['time_sum'] = sum(value)
        url_stat['time_max'] = max(value)
        url_stat['time_perc'] = round(url_stat['time_sum'] * 100 / (time_sum or 1), 2)  # div 0: if time_sum == 0
        url_stat['time_avg'] = url_stat['time_sum'] / (url_stat['count'])
        median = get_median_value_from_list(value)
        url_stat['time_med'] = median if median else 0
        result.append(url_stat)
    error = count_error_string * 100 / (count_log_string or 1)
    return result, error


def get_limit_report(urls_statistics: Dict, report_size: int) -> Optional[List]:
    """ возвращает данные для отчёта по URL с наибольшим временем обработки
    :param urls_statistics: словарь с данными по всем URL из файла логов NGINX
    :param report_size: кол-во URL выводимых в отчет
    :return: словарь с данными по URL или None - если исходный словарь пустой
    """
    if not urls_statistics:
        return None
    # сортируем список по ключу словаря 'time_sum'
    try:
        report_sort = sorted(urls_statistics, key=lambda x: x['time_sum'], reverse=True)
    except Exception:
        logging.exception('!WOW!')
        return None
    # возвращаем дынные по ограниченному колиеству URL
    result = report_sort[:report_size]
    return result


def save_report_to_html_file(report_path: str,
                             template_path: str,
                             report_data: List) -> bool:
    """ Записывает отчетные табличные данные в HTML файл
    :param report_path: - путь и имя файла с отчётом
    :param template_path: - путь и имя файла шаблона HTML отчета
    :param report_data: - отчет
    :return:
    """
    try:
        template_html_file = open(template_path)
    except Exception:
        logging.exception('Bad template HTML report file. "%s"' % template_path)
        return False
    template_report = ''.join(template_html_file.readlines())
    template_report = Template(template_report).safe_substitute(table_json=report_data)
    # открываем для записи файл HTML
    try:
        report_file = open(report_path, mode='w')
    except Exception:
        logging.exception('Bad HTML report file. "%s"' % report_path)
        return False
    # записываем отчет в HTML файл
    try:
        report_file.write(template_report)
    except Exception:
        logging.exception('Error write to HTML report file. "%s"' % report_path)
        return False
    return True


def main():
    config = get_config(CONFIG_DEFAULT, sys.argv)
    if not config:
        exit()
    log_dir = config['log_dir']
    report_dir = config['report_dir']
    pattern_logs_filename = config['pattern_logs_filename']

    logger = init_logging(config['logging_path'])
    if not logger:
        exit()
    last_logs_filename = get_last_logs_filename(log_dir, pattern_logs_filename)
    if not last_logs_filename:
        exit()
    report_filename = get_report_filename(last_logs_filename)
    if not report_filename:
        exit()
    result_flag = check_exist_reports_directory(report_dir)
    if not result_flag:
        exit()
    result_flag = check_exist_report_file(report_dir, report_filename)
    if result_flag:         # файл отчета уже существует, повторный анализ не производим, выход
        logging.info('HTML report file already exists. Reanalysis canceled')
        exit()
    result_data = get_statistics_logs(log_dir, last_logs_filename)
    if not result_data:
        exit()
    result_statistics, error_rate = result_data
    if error_rate > float(config['parsing_error']):
        logging.error('To many bad LOGS in file. Exit')
        exit()
    report_data = get_limit_report(result_statistics, int(config['report_size']))
    if not report_data:
        exit()

    report_path = os.path.join(report_dir, report_filename)
    report_template_path = os.path.join(config['report_template_dir'],
                                        config['report_template_filename'])
    result_flag = save_report_to_html_file(report_path, report_template_path, report_data)
    if not result_flag:
        exit()
    logging.info('Report successfully created: %s' % report_filename)
    print('Report successfully created: %s' % report_filename)


if __name__ == "__main__":
    main()
