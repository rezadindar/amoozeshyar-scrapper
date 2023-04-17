
# ربات استخراج اطلاعات کلاس ها از سامانه آموزشیار

برای راه اندازی مرورگر کروم بر روی سیستم عامل سنتوس از دستور زیر استفاده نمایید:

```
yum install chromium -y
```

برای نصب پیش نیاز ها و کتابخانه های پایتون:
```
pip install -r requirements.txt
```

همچنین برای نصب پایتون 3.8 در سنتوس 7:
```
yum --enablerepo=centos-sclo-rh -y install rh-python38 
```
```
nano .bash_profile
```
```
source scl_source enable rh-python38
```

# نحوه اجرا
برای اجرای اسکریپت از دستور زیر استفاده نمایید:
```
screen uvicorn amoozeshyar:app --reload --host=0.0.0.0
```
