import sqlite3
conn = sqlite3.connect('smart_vend.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM chat_messages')
print('Total messages:', c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id NOT LIKE 'manager:%'")
print('Public (non-manager) messages:', c.fetchone()[0])
c.execute('SELECT id, session_id, role, substr(content,1,60), created_at FROM chat_messages ORDER BY id DESC LIMIT 15')
rows = c.fetchall()
for r in rows:
    print(r)
conn.close()
