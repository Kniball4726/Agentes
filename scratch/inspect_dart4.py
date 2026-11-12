with open(r'C:\Users\user\Desktop\Software\DescuentoAgentico\Agentes\.venv\Lib\site-packages\flet_web\web\main.dart.js', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('.wC(')
while idx != -1:
    print(text[idx-100:idx+200])
    print("="*40)
    idx = text.find('.wC(', idx + 1)
