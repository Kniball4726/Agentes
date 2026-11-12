with open(r'C:\Users\user\Desktop\Software\DescuentoAgentico\Agentes\.venv\Lib\site-packages\flet\controls\page.py', encoding='utf-8') as f:
    text = f.read()

# Let's search how _services is updated or sent
idx = text.find('class ServiceRegistry')
idx2 = text.find('def register_service', idx)
print(text[idx2:idx2+1500])
