import io,sys,sqlite3
sys.stdout.reconfigure(encoding='utf-8')
c=sqlite3.connect('app/src/main/assets/translated.db')
print('rows containing <br>:', list(c.execute("select song_title, sentence from song_translations where english like '%<br>%' or japanese like '%<br>%'")))
print('FEHLT first row:', list(c.execute("select sentence, english, japanese from song_translations where song_title='FEHLT' and sentence like 'Elaisic%'")))
