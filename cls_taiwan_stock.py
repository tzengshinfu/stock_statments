from cls_webpage_fetcher import ClsWebpageFetcher
from cls_excel_handler import ClsExcelHandler
import datetime
from collections import namedtuple


# TODO 財務附註 http://mops.twse.com.tw/server-java/t164sb01
# http://mops.twse.com.tw/server-java/t164sb01
# http://mops.twse.com.tw/server-java/t164sb01?step=1&CO_ID=1101&SYEAR=2018&SSEASON=3&REPORT_ID=C
# http://mops.twse.com.tw/mops/web/t05st22_q1
# EPS改用程式計算
class ClsTaiwanStock():
    fetcher = ClsWebpageFetcher()
    excel = ClsExcelHandler()

    def get_financial_statement_files(self):
        config = self.excel.show_config_form()
        if config.action == 'Submit':
            self.excel.open_books_directory(config.drive_letter + '\\' + config.directory_name)
            stock_list = self.get_stock_list()
            self.get_basic_info_files(stock_list)
            self.get_statment_files(stock_list)
            self.excel.show_popup('建立完成。')
            self.excel.close_config_form()
        else:
            self.excel.show_popup('取消建立!')
            self.excel.close_config_form()

    def get_basic_info_files(self, stock_list: list):
        for stock in stock_list:
            book_path = self.excel.books_path + '\\' + stock.id + '(' + stock.name + ')' + '.xlsx'
            if not self.excel.is_book_existed(book_path):
                self.excel.open_book(book_path)
                self.fetcher.wait(2, 7)
                basic_info = self.__get_basic_info(stock.id)
                self.excel.write_to_sheet(basic_info)
                self.excel.save_book(book_path)

    def get_stock_list(self) -> list:
        """取得台股上巿股票代號/名稱列表

            Returns:
                {list} -- 股票代號/名稱列表
        """
        stock_list = []
        self.fetcher.go_to('http://www.twse.com.tw/zh/stockSearch/stockSearch')
        stock_datas = self.fetcher.find_elements('//table[@class="grid"]//a/text()')
        stock = namedtuple('stock', 'id name')
        for stock_data in stock_datas:
            stock.id = stock_data[0]
            stock.name = stock_data[1]
            stock_list.append(stock)
        return stock_list

    def __get_basic_info(self, stock_id: str) -> list:
        """取得台股上巿股票基本資料

            Arguments:
                stock_id {str} -- 股票代碼

            Returns:
                {list} -- 基本資料
        """
        basic_info = {}
        self.fetcher.go_to('http://mops.twse.com.tw/mops/web/t05st03', 'post', 'firstin=1&co_id=' + stock_id)
        row_tags = self.fetcher.find_elements('//table[@class="hasBorder"]//tr')
        title = ''
        for row_tag in row_tags:
            if (row_tag[0].text.strip() == '本公司'):
                basic_info[row_tag[2].text.strip()] = row_tag[1].text.strip()
                basic_info[row_tag[5].text.strip()] = row_tag[4].text.strip()
            if (row_tag[0].text.strip() == '本公司採'):
                basic_info['會計年度月制(現)'] = row_tag[1].text.strip()
            if (row_tag[0].text.strip() == '本公司於'):
                basic_info['會計年度月制(前)'] = row_tag[3].text.strip()
                basic_info['會計年度月制轉換'] = row_tag[1].text.strip()
            if (row_tag[0].text.strip() == '編製財務報告類型'):
                report_type = row_tag[1].text.strip()
                basic_info[row_tag[0].text.strip()] = report_type[1:3] if report_type[0] == '●' else report_type[4:6]
            else:
                for index, cell in enumerate(row_tag, start=1):
                    if (index % 2 == 1):
                        if (cell.tag == 'th'):
                            title = cell.text.strip()
                            basic_info[title] = ''
                    else:
                        if (cell.tag == 'td'):
                            basic_info[title] = cell.text.strip()
        basic_info_list = self.__convert_to_list(basic_info)
        return basic_info_list

    def __get_periods(self, top_n_seasons_count: int = 0) -> list:
        def get_season(month: str) -> str:
            mapping = {
                '1': '1',
                '2': '1',
                '3': '1',
                '4': '2',
                '5': '2',
                '6': '2',
                '7': '3',
                '8': '3',
                '9': '3',
                '10': '4',
                '11': '4',
                '12': '4'
            }
            return mapping.get(month)

        self.fetcher.go_to('http://mops.twse.com.tw/server-java/t164sb01')
        years = self.fetcher.find_elements('//select[@id="SYEAR"]//option/@value')
        current_year = str(datetime.datetime.now().year)
        current_season = get_season(str(datetime.datetime.now().month))
        periods = []
        period = namedtuple('period', 'year season')
        index = 0
        for year in reversed(years):
            for season in reversed(['1', '2', '3', '4']):
                if str(year + season) >= str(current_year + current_season):
                    continue
                index += 1
                if top_n_seasons_count != 0 and index > top_n_seasons_count:
                    return periods
                period.year = year
                period.season = season
                periods.append(period)
        return periods

    def get_table(self, table_type: str) -> list:
        """取得表格內容

            Arguments:
                stock_id {str} -- 股票代碼
                top_n_seasons_count {int} -- 取得前n季(0=全部)

            Returns:
                {list} -- 表格內容
        """

        if table_type == '資產負債表':
            item_xpath = '//table[@class="result_table hasBorder"]//tr[not(th)]'
        elif table_type == '損益表':
            item_xpath = '//table[@class="result_table hasBorder"]//tr[not(th)]'
        elif table_type == '股東權益表':
            item_xpath = '//table[@class="result_table hasBorder"]//tr[not(th)]'
        elif table_type == '現金流量表':
            item_xpath = '//table[@class="result_table hasBorder"]//tr[not(th)]'
        else:
            raise ValueError('類型只能是[資產負債表/損益表/股東權益表/現金流量表]其中之一')

        row_tags = self.fetcher.find_elements(item_xpath)
        records = []
        for row_tag in row_tags:
            record = []
            cell_tags = row_tag.xpath('./td[position() <= 2]')
            for cell_tag in cell_tags:
                record.append(cell_tag.text)
            records.append(record)
        return records

    def get_statment_files(self, stock_list):
        periods = self.__get_periods(0)

        for stock in stock_list:
            self.fetcher.wait(2, 7)
            self.fetcher.go_to('http://mops.twse.com.tw/server-java/t164sb01?step=1&CO_ID={0}&SYEAR={1}&SSEASON={2}&REPORT_ID=C'.format(stock_id, season[0], season[1]))
            self.get_xx(stock, periods, '資產負債表')
            self.get_xx(stock, periods, '損益表')
            self.get_xx(stock, periods, '股東權益表')
            self.get_xx(stock, periods, '現金流量表')

    def get_xx(self, stock, periods, table_type: str):
        financial_position_book_path = self.excel.books_path + '\\' + stock.id + '(' + stock.name + ')_{0}'.format(table_type) + '.xlsx'
        self.excel.open_book(financial_position_book_path)
        for period in periods:
            sheet_name = period.year + '_' + period.season
            if not self.excel.is_sheet_existed(sheet_name):
                self.excel.open_sheet(sheet_name)
                table = self.get_table(table_type)
                self.excel.write_to_sheet(table)

    def __convert_to_list(self, original_dict: dict)->list:
        converted_list = []
        for key, value in original_dict.items():
            converted_list.append([key, value])
        return converted_list
