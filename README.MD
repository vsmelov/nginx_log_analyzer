Log_analyzer написан на python 3.7.
Программа ищет последний (по дате в имени файла) файл в папке с лог файлами NGINX (шаблон имени файла: nginx-access-ui.log-20170630.gz). Анализирует найденный файл с логами NGINX и формирует HTML отчет, содержащий заданное количество URL c наибольшим временем обработки. В случае если отчет уже имеется, повторная обоработка файла с логами не производится.
В результате создается HTML файл с отчетом (например: report-2017.06.30.html)

Требования к логам NGINX: в конце лога должен быть добавлен $request_time.
 формат логов NGINX
 log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
                     '$status $body_bytes_sent "$http_referer" '
                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
                     '$request_time';
 
Дополнительная информация: в папку с отчетами необходимо скопировать файл "jquery.tablesorter.min.js

Примеры запуска программы:
	program.py
	program.py --config settings.ini
	python3 program.py --config settings.ini

По умолчанию имя файла с настройками (конфиг): 'settings.ini'. 
Файл с настройками можно изменить, указав в коммандной строке: '--config <filename>'

Параметры программы по умолчанию (настройки в конфиг файле имеют больший приоритет, чем настройки по умолчанию):
1. Файл журнала с логами выполнения программы, если параметр не указан в конфиг файле - вывод журнала логов осуществляется в stdout
	logging_path=error.log
2. Папка с файлами логов NGINX
	log_dir=logs
3. Шаблон имени файла с логами NGINX
	pattern_logs_filename='nginx-access-ui.log-\d{8}(.gz)*$'
4. Файл с шаблоном HTML отчета
	report_template_filename=report.html
5. Файл с шаблоном HTML отчета
	report_template_dir=./
6. Папка с HTML отчетами
	report_dir=report
7. Количество URL в HTML отчете c наибольшим временем обработки 
	report_size=1000
8. Процент порога ошибок при чтении лог файла NGINX
	parsing_error=50.0


HTML файл отчета содержит следующую информацию:
1. URL:						URL
2. Количество обращений к URL, шт.:		count 
3. Процент обращения к URL, %: 			count_perc
4. Суммарное время $request_time URL, мс.: 	time_sum 
5. Процент времени обработки URL, %: 		time_perc 
6. Среднее время обработки URL, мс.: 		time_avg 
7. Максимальное время обработки URL, мс.: 	time_max
8. Медиана времени обработки URL, мс.: 		time_med

