from tankwatch import Tank
args = ('2018-11-20 00:00:00', '2018-12-10 00:00:00', -1)
t = Tank()
# r = t.login('admin','')
# print(r.headers['Set-Cookie'])
r = t.failinfo(*args)
print(type(r), r.text)
r = t.get_failinfo_json(*args)
print('/n')
# for i in r:
#     print(i)
print(type(r), len(r))
