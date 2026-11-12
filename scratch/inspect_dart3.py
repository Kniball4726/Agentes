with open(r'C:\Users\user\Desktop\Software\DescuentoAgentico\Agentes\.venv\Lib\site-packages\flet_web\web\main.dart.js', encoding='utf-8', errors='ignore') as f:
    text = f.read()

idx = text.find('case"FilePicker":return new A.ats')
print(text[idx-500:idx+300])
