"""
inf-файл - структура всех данных и ввод из них

(C) 2020 Ivan Genik, Perm, Russia
Released under GNU Public License (GPL)
email igenik@rambler.ru
"""

import numpy as np
import copy
import math
import numba
import os
import pathlib
from pfunct import *
from pstring import *
from pmain_proc import *

test_mode = True  # тестовый режим
makroseis_folder: str = r"Work_Lang\Python\PyCharm\Makroseis"
makroseis_datfolder: str = r"Work_Lang\Python\PyCharm\Makroseis\Dat"
datfolder: str = r"Dat"
testxls_filename: str = r"точки_ввод.xls"
testtxt_filename: str = r"точки_ввод.txt"
testinf_filename: str = r"точки_ввод.inf"
test_restxt_filename: str = r"точки_ввод_res.txt"
test_resxls_filename: str = r"точки_ввод_res.xlsx"
nrow_testf: int = 48  # число строк в образцовом файле, включая строку заголовков столбцов
ncol_tes: int = 7  # число столцов в образцовом файле
is_txt_res_file: bool = False

# Словари (dict) и работа с ними. Методы словарей
#  https://pythonworld.ru/tipy-dannyx-v-python/slovari-dict-funkcii-i-metody-slovarej.html
# значения коэффициентов a, b, c макросейсмического уравнения по умолчанию, а также их миниммальные и максимальные значения
a_def = 1.5;      min_a = 0.001;  max_a = 1000.0
b_def = 3.17;     min_b = 0.001;  max_b = 1000.0
c_def = 2.71;     min_c = 0.001;  max_c = 1000.0
min_m = 0.0;      max_m = 10.0
min_lat = -90.0;  max_lat = 90.0
min_lon = -180.0; max_lon = 180.0
min_dep = 0.05;   max_dep = 300
lin_coeff = 8   # коэффициент для барьерной функции

# начальное периближение для минимизации - магнитуда, глубина
# https://cyberleninka.ru/article/n/seysmichnost-urala-i-prilegayuschih-territoriy
# Урал: За последние 300 лет в пределах рассматриваемого региона было отмечено около 50 ощутимых
# землетрясений интенсивностью от 3–4 до 5–6 баллов по шкале MSK-64
ini_mag = 4.5
# Урал: Очаги большей части природных ощутимых землетрясений рассматриваемого района локализованы
# в породах дорифейского кристаллического фундамента на глубинах от первых километров до 15–25 км
ini_dep = 12

txtfname_def = 'точки_ввод.txt'
inf_fname_def = 'точки_ввод.inf'
inf_fname_def_auto = 'точки_ввод_AUTO.inf'

# What is the maximum float in Python? == sys.float_info.max
# https://stackoverflow.com/questions/3477283/what-is-the-maximum-float-in-python
# пустой
inf_empydefdict = dict(name_sq='', fdat_name='',  # название площади, имя файла данных
                       a=float('nan'), b=float('nan'), c=float('nan'),
                       # коэффициенты a, b, c макросейсмического уравнения
                       min_mag=float('nan'), max_mag=float('nan'),  # минимальная и максимальная магнитуда
                       min_lat=float('nan'), max_lat=float('nan'),  # минимальная и максимальная широта
                       min_lon=float('nan'), max_lon=float('nan'),  # минимальная и максимальная долгота
                       min_dep=float('nan'), max_dep=float('nan'),  # минимальная и максимальная глубина
                       ini_lat=float('nan'), ini_lon=float('nan'),  # начальное периближение для минимизации - широта, долгота
                       ini_mag=float('nan'), ini_dep=float('nan'),  # начальное периближение для минимизации - магнитуда, глубина
                       calc_ini=False, # внутреняя информация -  надо ли самому расчитывать начальное приближение
                       work_dir='',  # внутреняя информация - папка с данными,
                       finf_name='', # внутреняя информация - имя inf-файла
                       npoint=float('nan') # внутреняя информация - число точек в файле *.txt или xlsx
                       )

# Файл тестовый
inf_defdict = dict(name_sq='Новозаречный', fdat_name=txtfname_def,  # название площади, имя файла данных
                   a=a_def, b=b_def, c=c_def,  # коэффициенты a, b, c макросейсмического уравнения
                   min_mag=0.0, max_mag=10.0,  # минимальная и максимальная магнитуда
                   min_lat=float('nan'), max_lat=float('nan'),  # минимальная и максимальная широта
                   min_lon=float('nan'), max_lon=float('nan'),  # минимальная и максимальная долгота
                   min_dep=float('nan'), max_dep=float('nan'),  # минимальная и максимальная глубина
                   ini_lat=float('nan'), ini_lon=float('nan'),  # начальное периближение для минимизации
                   calc_ini=False,  # внутреняя информация -  надо ли самому расчитывать начальное приближение
                   work_dir='',  # внутреняя информация о папке с данными
                   finf_name='', # внутреняя информация - имя inf-файла
                   npoint = float('nan')  # внутреняя информация - число точек в файле *.txt или xlsx
                   )

# Как я могу проверить, пуст numpy или нет?
# https://techarks.ru/qa/python/kak-ya-mogu-proverit-pust-n-10/

#--------- Квази объект "Структура данных" - (Начало)
curr_nstruct = -1  # номер структуры данных; -1 - нет данных, 0 - первая и т.д.
dat_struct: np.ndarray  # пустой набор данных в начале
out_of_range = np.zeros(4, dtype=int)  # cколько раз переменная выходила за границы переменная

def add_dat_struct(the_dict, the_nparray): # добавление данных в структуру dat_struct
    global dat_struct
    global curr_nstruct
    curr_nstruct = curr_nstruct+1
    if curr_nstruct == 0:
        dat_struct = create_2d_nparray_r1c2(1, 2, the_dict, the_nparray)
    else:
        dat_struct = add_2d_nparray(dat_struct, the_dict, the_nparray)


def get_dat_struct(num_el: int):  # извлечение данных из структуры dat_struct
    global dat_struct
    a = dat_struct[num_el, 0]
    b = dat_struct[num_el, 1]
    return a, b

def get_a_b_c(num_el: int):  # извлечение коэффициентов a, b, c макросейсмического уравнения из структуры dat_struct
    global dat_struct
    get_dat_struct(num_el)
    the_dict = dict(dat_struct[num_el, 0])
    a_ = the_dict["a"]
    b_ = the_dict["b"]
    c_ = the_dict["c"]
    return a_, b_, c_

def get_ini(num_el: int):  # извлечение ini_lat, ini_lon, ini_dep, ini_mag
    global dat_struct
    get_dat_struct(num_el)
    the_dict = dict(dat_struct[num_el, 0])
    ini_lat_ = the_dict["ini_lat"] # начальное периближение для минимизации - широта
    ini_lon_ = the_dict["ini_lon"] # начальное периближение для минимизации - долгота
    ini_dep_ = the_dict["ini_dep"]  # начальное периближение для минимизации - глубина
    ini_mag_ = the_dict["ini_mag"]  # начальное периближение для минимизации - магнитуда
    return ini_lat_, ini_lon_, ini_dep_, ini_mag_

def get_lim_magn_lat_lon_dep(num_el: int) -> (float, float, float, float, float, float, float, float):
    """
    извлечение данных из структуры dat_struct - границы magn, lat, lon, dep
    """
    global dat_struct
    get_dat_struct(num_el)
    a = dict(dat_struct[num_el, 0])
    min_mag_ = a["min_mag"]; max_mag_ = a["max_mag"]
    min_lat_ = a["min_lat"]; max_lat_ = a["max_lat"]
    min_lon_ = a["min_lat"]; max_lon_ = a["max_lon"]
    min_dep_ = a["min_dep"]; max_dep_ = a["max_dep"]
    # print(min_mag_, max_mag_, min_lat_, max_lat_, min_lon_, max_lon_, min_dep_, max_dep_)
    return min_mag_, max_mag_, min_lat_, max_lat_, min_lon_, max_lon_, min_dep_, max_dep_


def print_dat_struct() -> None:
    print(dat_struct)

#--------- Квази объект "Структура данных" - (Конец)

def work_with_line3dat(s: str):  # строка с коэффициентами макросейсмического уравнения
    part_lines2 = s.split(maxsplit=3)  # print_string(part_lines)
    a = float(part_lines2[0])
    b = float(part_lines2[1])
    c = float(part_lines2[2])
    return a, b, c


def work_with_line2dat(s: str):  # строка с "минимальная и максимальная магнитуда"
    part_lines2 = s.split(maxsplit=2)
    a = float(part_lines2[0])
    b = float(part_lines2[1])
    return a, b


def control_curr_dict(curr_dict: dict) -> bool:
    """
    Контроль информации из inf-файла
    """
    full_file_name: str = "\\".join([curr_dict["work_dir"], curr_dict["fdat_name"]])
    path = pathlib.Path(full_file_name)
    if not path.exists():
        print('путь к dat-файлу не существует = ', full_file_name)
        return False
    if not path.is_file():
        print('dat-файл не существует = ', full_file_name)
        return False
    # Далее проверки на попадание в диапазон
    int_a = dat_in_diap(curr_dict["a"], min_a, max_a)
    int_b = dat_in_diap(curr_dict["b"], min_b, max_b)
    int_c = dat_in_diap(curr_dict["c"], min_c, max_c)
    if not (int_a and int_b and int_c):
        print('Ошибка в коэффициентах макросейсмического уравнения')
        return False
    int_m = dat2_in_diap(curr_dict["min_mag"], curr_dict["max_mag"], min_m, max_m)
    if not int_m:
        print('Ошибка в диапазоне магнитуд')
        # print(curr_dict["min_mag"], curr_dict["max_mag"], min_m, max_m)
        return False
    int_lat = dat2_in_diap(curr_dict["min_lat"], curr_dict["max_lat"], min_lat, max_lat)
    if not int_lat:
        print('Ошибка в диапазоне широт')
        return False
    int_lon = dat2_in_diap(curr_dict["min_lon"], curr_dict["max_lon"], min_lat, max_lat)
    if not int_lon:
        print('Ошибка в диапазоне долгот')
        return False
    int_dep = dat2_in_diap(curr_dict["min_dep"], curr_dict["max_dep"], min_dep, max_dep)
    if not int_dep:
        print('Ошибка в диапазоне глубин')
        return False
    if not curr_dict["calc_ini"]:
        int_ini1 = dat_in_diap(curr_dict["ini_lat"], min_lat, max_lat)
        int_ini2 = dat_in_diap(curr_dict["ini_lon"], min_lon, max_lon)
        if not (int_ini1 and int_ini2):
            print('Ошибка в начальном приближении')
            return False
    return True


def input_inf(fname, is_view=False) -> (bool, object):
    """
    Ввод информации из файлв
    """
    s: str; s2: str
    # if isview: print('fname =', fname)
    # https://askdev.ru/q/numpy-dobavit-stroku-v-massiv-20857/
    file_exist: bool = os.path.isfile(fname)
    if not file_exist:
        return file_exist, inf_empydefdict
    else:
        f = open(fname, 'r')
        all_lines = f.read().splitlines()  # разделяет строку по символу переноса строки \n. Возвращает список(list)
        nrow1 = len(all_lines)  # вместе со строкой заголовков
        curr_dict = copy.deepcopy(inf_empydefdict)
        for i in range(nrow1):
            # Кракозябры в PyCharm
            # https://python.su/forum/topic/27557/
            s = all_lines[i].encode('cp1251').decode('utf-8')  # перекодировка из Win в UTF
            s = s.strip()  # пробелы лишние убираем
            all_lines[i] = s  # на всякий случай сохраняем
            part_lines = s.split(sep=';', maxsplit=2)  # print_string(part_lines)
            if i == 0:
                curr_dict["name_sq"] = part_lines[0].strip()
            elif i == 1:
                curr_dict["fdat_name"] = part_lines[0].strip()
            elif i == 2:
                (curr_dict["a"], curr_dict["b"], curr_dict["c"]) = work_with_line3dat(part_lines[0].strip())
            elif i == 3:
                (curr_dict["min_mag"], curr_dict["max_mag"]) = work_with_line2dat(part_lines[0].strip())
            elif i == 4:
                (curr_dict["min_lat"], curr_dict["max_lat"]) = work_with_line2dat(part_lines[0].strip())
            elif i == 5:
                (curr_dict["min_lon"], curr_dict["max_lon"]) = work_with_line2dat(part_lines[0].strip())
            elif i == 6:
                (curr_dict["min_dep"], curr_dict["max_dep"]) = work_with_line2dat(part_lines[0].strip())
            elif i == 7:
                s2 = part_lines[0].strip()
                n = num_words_in_string(s2)
                if n==2:
                    (curr_dict["ini_lat"], curr_dict["ini_lon"]) = work_with_line2dat(s2)
                    curr_dict["calc_ini"] = False
                elif n==1:
                    dd:float = float(re.sub(r'\D', '', s2))
                    curr_dict["calc_ini"] = True
                    curr_dict["ini_lat"] = -dd
                    curr_dict["ini_lon"] = -dd
                else:
                    curr_dict["calc_ini"] = True
                    curr_dict["ini_lat"] = -1
                    curr_dict["ini_lon"] = -1

    # Запоминаем путь к файлу данных
        # https://python-scripts.com/pathlib
        curr_dict["work_dir"] = str(pathlib.Path(fname).parent)
        curr_dict["finf_name"] = str(pathlib.Path(fname).name)
    # начальное периближение для минимизации - магнитуда, глубина
        curr_dict["ini_mag"] = ini_mag
        curr_dict["ini_dep"] = ini_dep
        if is_view: print(curr_dict)
        return file_exist, curr_dict

# @numba.njit
def calc_distance(lat_arr: float, lon_arr: float, h_arr: float, lat: float, lon: float, dep: float)-> float:
    """
    Вычисление расстояния (км) между 2 точками с заданными координатами
    h_arr, dep - в км
    """
    len_pnt: float = calc_geogr_dist(lat_arr, lon_arr, lat, lon)
    dat:float = math.sqrt(len_pnt**2 +(h_arr + dep)**2 )
    return dat

# @numba.njit
def objective_function(n: int, Lat_arr, Lon_arr, H_Arr, I_fact_Arr,
                       lat_: float, lon_: float, dep_: float, mag_:float,
                       a: float, b: float, c: float )-> float:
    """
    Функция для минимизации
    Входные данные
    n - число точек, param Lat_arr - массив широт, Lon_arr - массив долгот
    H_Arr - массив высот, I_fact_Arr - массив фактическая интенсивность
    Очаг: lat_ - текущая широта, lon_ - текущая долгота, depth_ - текущая глубина, magn_ - магнитуда
    a, b, c - коэффициенты макросейсмического уравнения
    Выходные данные - значения функции
    """
    global curr_nstruct
    f_curr: float
    (min_mag_, max_mag_, min_lat_, max_lat_, min_lon_, max_lon_, min_dep_, max_dep_) = get_lim_magn_lat_lon_dep(curr_nstruct)
    f: float =0;
    dist: float
    addd: float
    # print(a, b, c)
    for i in range(n):
        # ind_print: bool = False
        #- Основная часть функции - сумма квадратов разностей
        dist = calc_distance(Lat_arr[i], Lon_arr[i], H_Arr[i], lat_, lon_, dep_)
        #  Первональный вариант технического задания
        # Imod = a*mag_ - b*math.log10(dist) + c
        # Второй вариант, 2007_Уpавнение макpоcейcмичеcкого поля c конвеpгентным pешением_Потапов.pdf, стр, 882, формула 3
        Imod = a*mag_ - b*math.log10(dist + 0.0185*pow(10, 0.43*mag_)) + c
        dat = (I_fact_Arr[i]- Imod)
        f_curr = pow(dat,2)
        f = f + f_curr
#       f1 = copy.deepcopy(f)
        #- Дополнительные части функции - барьерные функции по каждой переменной
        if not dat_in_diap(lat_, min_lat_, max_lat_):
            ou_lat_ = out_of_diap1proc(lat_, min_lat_, max_lat_)
            addd = lin_coeff*f_curr*ou_lat_
            f = f + addd
            # out_of_range[0] += 1
            # ind_print = True; print('ou_lat_=', ou_lat_, end=' ')
        if not dat_in_diap(lon_, min_lon_, max_lon_):
            ou_lon_ = out_of_diap1proc(lon_, min_lon_, max_lon_)
            addd = lin_coeff * f_curr * ou_lon_
            f = f + addd
            # out_of_range[1] += 1
            # ind_print = True; print('ou_lon_=', ou_lon_, end=' ')
        if not dat_in_diap(dep_, min_dep_, max_dep_):
            # print('dep_=',dep_, end=' ')
            ou_dep = out_of_diap2proc(dep_, min_dep_, max_dep_)
            # out_of_range[2] += 1
            # ind_print = True; print('ou_dep =',ou_dep, end=' ')
            addd = lin_coeff*f_curr*ou_dep
            f = f + addd
        if not dat_in_diap(mag_, min_mag_, max_mag_):
            # print('mag_=', mag_)
            ou_mag = out_of_diap1proc(mag_, min_mag_, max_mag_)
            # out_of_range[3] += 1
            # ind_print = True; print('ou_mag =',ou_mag, end=' ')
            addd = lin_coeff*f_curr*ou_mag
            f = f +addd
        # if ind_print: print()
    return f

def result_control(lat_: float, lon_: float, dep_: float, mag_:float) -> None:
    indiap:bool
    ii:int
    print('Контроль результатов')

    (a, b, c) = get_a_b_c(curr_nstruct)
    (the_dict, the_arr) = get_dat_struct(curr_nstruct)
    row = the_dict["npoint"]

    lat_arr = the_arr[:, 0] # Lat
    # print('lat_arr ', np.size(lat_arr)); print(lat_arr)
    lon_arr = the_arr[:, 1] # Lat
    # print('lon_arr ', np.size(lon_arr)); print(lon_arr)
    h_arr = the_arr[:, 2]/1000 # Alt переводим в км
    # print('h_arr ', np.size(h_arr)); print(h_arr)
    i_fact_arr = the_arr[:, 3]
    # print('i_fact_arr ', np.size(i_fact_arr)); print(i_fact_arr)

    di = the_arr[:, 4]
    # print('di ', np.size(di)); print(di)
    imod = np.zeros(row)
    i_left_edge = i_fact_arr - di
    i_right_edge = i_fact_arr + di
    ii = 0
    for i in range(row):
        dist = calc_distance(lat_arr[i], lon_arr[i], h_arr[i], lat_, lon_, dep_)
        imod [i] = a*mag_ - b*math.log10(dist + 0.0185*pow(10, 0.43*mag_)) + c
        indiap = dat_in_diap(imod [i], i_left_edge[i], i_right_edge[i])
        ii = ii + int(indiap)
        print(i,' ',indiap, '   ', i_left_edge[i], imod [i], i_right_edge[i])
    print('Всего значений в диапазоне ', ii)





