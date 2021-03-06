from cls_webpage_fetcher import ClsWebpageFetcher
from cls_excel_handler import ClsExcelHandler
import datetime
from lxml import etree
from typing import List
from typing import Union
from typing import NamedTuple
import PySimpleGUI as gui
from functools import wraps
from win10toast import ToastNotifier


class ClsTaiwanStock():
    def __init__(self):
        self._fetcher = ClsWebpageFetcher()
        self._excel = ClsExcelHandler()
        self._current_process_count: int = 0
        self._total_process_count: int = 0
        self.books_path: str = ''
        self.notifier = ToastNotifier()

    def main(self):
        try:
            config = self.show_config_form()
            if config.action == 'Submit':
                self.books_path = config.drive_letter + ':\\' + config.directory_name
                self._excel.open_books_directory(self.books_path)
                self.get_stock_files(config)
                self.notifier.show_toast('Stock Statments', '建立完成')
            else:
                self.show_popup('取消建立!')
        except ValueError as ex:
            gui.Popup(ex)

    def show_current_process(function):
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            func = function(self, *args, **kwargs)
            self._current_process_count += 1
            self.notifier.show_toast('Stock Statments', '完成進度:' + str(round((self._current_process_count / self._total_process_count * 100), 2)) + '%', duration=1)
            return func
        return wrapper

    @show_current_process
    def get_basic_info_files(self, stock: NamedTuple('stock', [('id', str), ('name', str)])):
        """
        取得台股上巿股票基本資料檔案

        Arguments:
        stock -- 股票代號/名稱
        """
        def get_basic_info() -> List[List[str]]:
            """
                取得台股上巿股票基本資料

                Returns:
                基本資料
                """
            basic_info = dict()

            html = self._fetcher.download_html('http://mops.twse.com.tw/mops/web/t05st03', 'post', 'firstin=1&co_id=' + stock.id)

            title = ''
            rows = self._fetcher.find_elements(html, '//table[@class="hasBorder"]//tr')
            for row in rows:
                if (row[0].text.strip() == '本公司'):
                    basic_info[row[2].text.strip()] = row[1].text.strip()
                    basic_info[row[5].text.strip()] = row[4].text.strip()
                if (row[0].text.strip() == '本公司採'):
                    basic_info['會計年度月制(現)'] = row[1].text.strip()
                if (row[0].text.strip() == '本公司於'):
                    basic_info['會計年度月制(前)'] = row[3].text.strip()
                    basic_info['會計年度月制轉換'] = row[1].text.strip()
                if (row[0].text.strip() == '編製財務報告類型'):
                    report_type = row[1].text.strip()
                    basic_info[row[0].text.strip()] = report_type[1:3] if report_type[0] == '●' else report_type[4:6]
                else:
                    for index, cell in enumerate(row, start=1):
                        if (index % 2 == 1):
                            if (cell.tag == 'th'):
                                title = cell.text.strip()
                                basic_info[title] = ''
                        else:
                            if (cell.tag == 'td'):
                                basic_info[title] = cell.text.strip()
            basic_info_list = self._to_list(basic_info)

            return basic_info_list

        book_path = self.books_path + '\\' + stock.id + '(' + stock.name + ')_基本資料' + '.xlsx'
        if not self._excel.is_book_existed(book_path):
            self._fetcher.wait(30, 35)
            self._excel.open_book(book_path)
            basic_info = get_basic_info()
            self._excel.write_to_sheet(basic_info)
            self._excel.save_book(book_path)

    def get_stock_list(self, start_stock_id: str, finish_stock_id: str) -> List[NamedTuple('stock', [('id', str), ('name', str)])]:
        """
        取得台股上巿股票代號/名稱列表

        Returns:
        股票代號/名稱列表
        """
        stock_list = list()

        html = self._fetcher.download_html('http://www.twse.com.tw/zh/stockSearch/stockSearch')

        stock_items = self._fetcher.find_elements(html, '//table[@class="grid"]//a/text()')
        for stock_item in stock_items:
            stock = NamedTuple('stock', [('id', str), ('name', str)])
            stock.id = stock_item[0:4]
            stock.name = stock_item[4:]
            if stock.id >= (start_stock_id if start_stock_id != '' else '0000') and stock.id <= (finish_stock_id if finish_stock_id != '' else '9999'):
                stock_list.append(stock)
        return stock_list

    def _get_periods(self, start_season: str, finish_season: str) -> List[NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])]:
        html = self._fetcher.download_html('http://mops.twse.com.tw/server-java/t164sb01')

        years = self._fetcher.find_elements(html, '//select[@id="SYEAR"]//option/@value')
        current_year = datetime.datetime.now().year

        periods = list()

        for year in reversed(years):
            if int(year) <= current_year:
                first_season_date = datetime.datetime(int(year), 5, 15)
                second_season_date = datetime.datetime(int(year), 8, 14)
                third_season_date = datetime.datetime(int(year), 11, 14)
                fourth_season_date = datetime.datetime(int(year) + 1, 3, 31)

                for season in reversed(['01', '02', '03', '04']):
                        if ((season == '01' and datetime.datetime.now() > first_season_date) or
                                (season == '02' and datetime.datetime.now() > second_season_date) or
                                (season == '03' and datetime.datetime.now() > third_season_date) or
                                (season == '04' and datetime.datetime.now() > fourth_season_date)):
                            period = NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])
                            period.ad_year = year
                            period.roc_year = str(int(year) - 1911)
                            period.season = season
                            periods.append(period)

        return periods[int((start_season if start_season != '' else '1')) - 1:int(finish_season if finish_season != '' else str(len(periods)))]

    @show_current_process
    def get_statment_file(self, table_type: str, stock: NamedTuple('stock', [('id', str), ('name', str)]), period: NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])):
        """
        取得財務狀況Excel檔案

        Arguments:
        table_type -- 表格類型(資產負債表/綜合損益表/權益變動表/現金流量表/財報附註/財務分析/股利分配/會計報告)
        stock -- 股票代碼
        period -- 年度季別
        """

        def get_statment_table() -> List[str]:
            """
            取得表格內容

            Returns:
            表格內容
            """
            if table_type == '資產負債表':
                row_xpath = '//table[@class="hasBorder"]//tr[not(th)]'
                cell_xpath = './td[position() <= 3]'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t164sb03'
                data = 'encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryName=co_id&inpuType=co_id&TYPEK=all&isnew=false&co_id={0}&year={1}&season={2}'.format(stock.id, period.roc_year, period.season)
            elif table_type == '綜合損益表':
                row_xpath = '//table[@class="hasBorder"]//tr[not(th)]'
                cell_xpath = './td[position() <= 3]'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t164sb04'
                data = 'encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryName=co_id&inpuType=co_id&TYPEK=all&isnew=false&co_id={0}&year={1}&season={2}'.format(stock.id, period.roc_year, period.season)
            elif table_type == '現金流量表':
                row_xpath = '//table[@class="hasBorder"]//tr[not(th)]'
                cell_xpath = './td[position() <= 2]'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t164sb05'
                data = 'encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryName=co_id&inpuType=co_id&TYPEK=all&isnew=false&co_id={0}&year={1}&season={2}'.format(stock.id, period.roc_year, period.season)
            elif table_type == '權益變動表':
                row_xpath = '//table[@class="hasBorder" and position() = 2]//tr[position() >=3]'
                cell_xpath = './*'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t164sb06'
                data = 'encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryName=co_id&inpuType=co_id&TYPEK=all&isnew=false&co_id={0}&year={1}&season={2}'.format(stock.id, period.roc_year, period.season)
            elif table_type == '財報附註':
                row_xpath = '//table[@class="main_table hasBorder" and contains(., "財報附註")]//tr[position() >= 2]'
                cell_xpath = './td'
                url = 'http://mops.twse.com.tw/server-java/t164sb01'
                data = 'step=1&CO_ID={0}&SYEAR={1}&SSEASON={2}&REPORT_ID=C'.format(stock.id, period.ad_year, period.season.replace("0", ""))
            elif table_type == '財務分析':
                row_xpath = '//table[@style = "width:90%;"]//tr[position() >= 2]'
                cell_xpath = './th[@style = "text-align:left !important;"] | ./td[position() = 3]'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t05st22'
                data = 'encodeURIComponent=1&run=Y&step=1&TYPEK=sii&year={1}&isnew=false&co_id={0}&firstin=1&off=1&ifrs=Y'.format(stock.id, period.roc_year)
            elif table_type == '股利分配':
                row_xpath = '//table[@class="hasBorder"]//tr'
                cell_xpath = './*'
                url = 'http://mops.twse.com.tw/mops/web/ajax_t05st09'
                data = 'encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryName=co_id&inpuType=co_id&TYPEK=all&isnew=false&co_id={0}&year={1}'.format(stock.id, period.roc_year)
            elif table_type == '會計報告':
                row_xpath = '//table[@class="main_table hasBorder" and contains(., "會計師查核報告")]//tr[position() >= 2]'
                cell_xpath = './td'
                url = 'http://mops.twse.com.tw/server-java/t164sb01'
                data = 'step=1&CO_ID={0}&SYEAR={1}&SSEASON={2}&REPORT_ID=C'.format(stock.id, period.ad_year, period.season.replace("0", ""))
            else:
                raise ValueError('table_type值只能是(資產負債表/綜合損益表/權益變動表/現金流量表/財報附註/財務分析/股利分配/會計報告)其中之一')

            records = list()

            html = self._fetcher.download_html(url, 'post', data)
            rows = self._fetcher.find_elements(html, row_xpath)

            for row in rows:
                record = list()
                cells = row.xpath(cell_xpath)
                for cell in cells:
                    record.append(''.join(cell.itertext()).strip())
                records.append(record)

            return records

        book_path = self.books_path + '\\' + stock.id + '(' + stock.name + ')_{0}'.format(table_type) + '.xlsx'
        self._excel.open_book(book_path)

        sheet_name = period.ad_year + '_' + period.season
        if not self._excel.is_sheet_existed(sheet_name):
            self._fetcher.wait(30, 35)
            self._excel.open_sheet(sheet_name)
            table = get_statment_table()
            self._excel.write_to_sheet(table)
        self._excel.save_book(book_path)

    def _to_list(self, source: Union[dict, etree.Element]) -> List[List[str]]:
        result = list()

        if type(source) is dict:
            for key, value in source.items():
                result.append([key, value])
            return result
        elif type(source) is etree._Element:
            for row in source:
                record = list()
                for cell in row:
                    record.append(cell.text)
                result.append(record)
            return result

        return result

    def show_config_form(self) -> NamedTuple('result', [('action', str), ('drive_letter', str), ('directory_name', str), ('start_stock_id', str), ('finish_stock_id', str), ('start_season', str), ('finish_season', str)]):
        """
        開啟設定介面

        Returns:
        設定結果(執行動作+磁碟代號+目錄名稱+前n季)
        """
        form = gui.FlexForm('設定台股上巿股票Excel存放路徑')
        layout = [
            [gui.Text('請輸入下載Excel存放的磁碟代號及目錄名稱')],
            [gui.Text('磁碟代號', size=(15, 1), key='Drive'), gui.InputText('D')],
            [gui.Text('目錄名稱', size=(15, 1), key='Folder'), gui.InputText('Excel')],
            [gui.Text('請輸入起始股票代碼(未輸入=不限)')], [gui.Text('代碼', size=(15, 1), key='StartStockId'), gui.InputText('')],
            [gui.Text('請輸入結束股票代碼(未輸入=不限)')], [gui.Text('代碼', size=(15, 1), key='FinishStockId'), gui.InputText('')],
            [gui.Text('請輸入起始季數(未輸入=不限)')], [gui.Text('季數', size=(15, 1), key='StartSeason'), gui.InputText('1')],
            [gui.Text('請輸入結束季數(未輸入=不限)')], [gui.Text('季數', size=(15, 1), key='FinishSeason'), gui.InputText('1')],
            [gui.Submit(), gui.Cancel()]
            ]
        window = form.Layout(layout)
        return_values = window.Read()

        window.Close()

        result = NamedTuple('result', [('action', str), ('drive_letter', str), ('directory_name', str), ('start_stock_id', str), ('finish_stock_id', str), ('start_season', str), ('finish_season', str)])
        result.action = return_values[0]
        result.drive_letter = return_values[1][0]
        result.directory_name = return_values[1][1]
        result.start_stock_id = return_values[1][2]
        result.finish_stock_id = return_values[1][3]
        result.start_season = return_values[1][4]
        result.finish_season = return_values[1][5]

        return result

    def show_popup(self, message: str):
        """
        顯示跳顯訊息

        Arguments:
        message -- 訊息文字
        """
        gui.Popup(message)
        pass

    def get_stock_files(self, config: NamedTuple('result', [('action', str), ('drive_letter', str), ('directory_name', str), ('start_stock_id', str), ('finish_stock_id', str), ('start_season', str), ('finish_season', str)])):
        stock_list = self.get_stock_list(config.start_stock_id, config.finish_stock_id)
        stock_count = len(stock_list)
        periods = self._get_periods(config.start_season, config.finish_season)
        period_count = len(periods)
        roc_years = self._get_roc_years(periods)
        roc_year_count = len(roc_years)
        self._total_process_count = stock_count + (stock_count * roc_year_count) + (stock_count * period_count * 7)

        for stock in stock_list:
            self.get_basic_info_files(stock)
            for roc_year in roc_years:
                self.get_analysis_file(stock, roc_year)
                for period in periods:
                    if (roc_year == period.roc_year):
                        self.get_statment_files(stock, period)

    def get_statment_files(self, stock: NamedTuple('stock', [('id', str), ('name', str)]), period: NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])):
        self.get_statment_file('資產負債表', stock, period)
        self.get_statment_file('綜合損益表', stock, period)
        self.get_statment_file('現金流量表', stock, period)
        self.get_statment_file('權益變動表', stock, period)
        self.get_statment_file('財報附註', stock, period)
        self.get_statment_file('股利分配', stock, period)
        self.get_statment_file('會計報告', stock, period)

    def _get_roc_years(self, periods: List[NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])]):
        years = list()

        for period in periods:
            years.append(period.roc_year)

        return years

    def get_analysis_file(self, stock: NamedTuple('stock', [('id', str), ('name', str)]), roc_year: str):
        period = NamedTuple('period', [('roc_year', str), ('ad_year', str), ('season', str)])
        period.roc_year = roc_year
        period.ad_year = str(int(roc_year) + 1911)
        period.season = "00"
        self.get_statment_file('財務分析', stock, period)
