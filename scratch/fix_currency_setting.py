"""Fix stale currency setting in the project database."""
import sqlite3

db = r'C:\Users\Consar-Kilpatrick\Desktop\Apinto_Test\Apinto_Test\Project Database\Apinto_Test.db'
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("UPDATE settings SET value=? WHERE key=?", ('USD ($)', 'currency'))
conn.commit()
c.execute("SELECT key, value FROM settings WHERE key='currency'")
print("Updated:", c.fetchone())
conn.close()
print("Done")
