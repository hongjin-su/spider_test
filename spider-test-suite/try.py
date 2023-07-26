import sqlite3

con = sqlite3.connect('/Users/harry/Desktop/spider_dataset/database/concert_singer/concert_singer.sqlite')
cur = con.cursor()
pred = cur.execute('SELECT Year as Number_of_Concerts FROM concert GROUP BY Year ORDER BY Number_of_Concerts DESC LIMIT 1')
print(pred.fetchall())
gold = cur.execute('SELECT YEAR FROM concert GROUP BY YEAR ORDER BY count(*) DESC LIMIT 1')
print(gold.fetchall())