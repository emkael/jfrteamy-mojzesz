import logging, sys


class TeamyDB(object):

    db_cursor = None

    def __init__(self, settings):
        reload(sys)
        sys.setdefaultencoding("latin1")
        import mysql.connector
        self.database = mysql.connector.connect(
            user=settings['user'],
            password=settings['password'],
            host=settings['host'],
            port=settings.get('port', 3306),
            database=settings['database'])
        self.db_cursor = self.database.cursor(buffered=True)
        self.db_name = settings['database']

    def get_cursor(self):
        return self.db_cursor

    def __execute_query(self, sql, params):
        logging.debug('query (%s): %s | %s' % (self.db_name, sql.replace('\n', ' '), params))
        self.db_cursor.execute(sql, params)

    def fetch(self, sql, params=None):
        import mysql.connector
        try:
            self.__execute_query(sql, params)
            row = self.db_cursor.fetchone()
            return row
        except mysql.connector.Error as e:
            logging.error(str(e))
            raise IOError(e.errno, str(e), sql)

    def fetch_all(self, sql, params=None):
        import mysql.connector
        try:
            self.__execute_query(sql, params)
            results = self.db_cursor.fetchall()
            return results
        except mysql.connector.Error as e:
            logging.error(str(e))
            raise IOError(
                e.errno, str(e), sql)
