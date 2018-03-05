# Introduction

为了锻炼自己完成一个完整项目的能力以及一些其它的原因，做出了这个项目。实践意义大于实际意义吧~

虽然这个项目本意是抢一条微博的第一条评论(俗称沙发).但是真正显示评论的时候,默认是根据热度（以及可选的根据时间，你将排在最后...）排名来显示的。所以将自己喜欢的一句话或者你想表达的在`config`里进行设置，或许更好~
# Requirements
* Python 3+ (Recommended: 3.4+)

# Installation

`pip install -U weibo-sofa`

# Usage

1.Write run.py：

```

# coding=utf-8

from weibo import Client

usr = ***   # your username
pwd = ***   # your password

# `config` is the filename you should write next
client = Client(usr, pwd, 'config')
print('start run ')
client.run()
print('run over')

```

2.Write `config`:
```
RECORD_PATH = 'record'

# comment content
CONTENT = '沙发'

# sleep after a loop
INTERVAL = (1, 1.5, 2)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~
# 需要抢其沙发的用户uid
# 工大后院儿
UID = ['3779018282'，’3779018283']
```
**RECORD_PATH**: 对keys为session cookies,uids,uid_mid
的字典序列化后存放的路径

**CONTENT**：自定义微博评论的内容

**INTERVAL**: 间隔时间，防止被禁（每次会随机选择一个作为休眠时间）

**UID**：用户所属的uid

NOTE : 在Linux OS 上，你可以在terminal内，输入命令`weibo add -u uid_you_want_add -p record_filepath`来在程序运行时动态添加删除uid

3.Run run.py,and the result:

![](/img/weibo_result.png)


## 实现过程

1.登录

附上一张之前做的weibo登录流程图：
![Weibo Login](/img/weibo_login.png)

**Note**: prelogin url带了一个参数`checkpin=1`用来检测此账号登录是否需要验证码（图懒得改了）

微博登录具体过程就不表了，意义不大。这里主要列举一下需要主要的点：

* RSA加密 

* 一些请求头是必不可少的，譬如：X-Requested-With ,headers , Referer 
(这里必须要提一下referer,我在微博评论请求的发送被它卡住很久，因为我构造的是 Refer ,经室友细心指出才发现是拼错了...
更有意思的是，Referer的正确英语拼法是referrer。由于早期HTTP规范的拼写错误，为了保持向后兼容就将错就错了。
)

* 当登录需要验证码时，有时即使你验证码输对了，也会刷新验证码让你再输一次。不知道是微博的Bug还是Feature。

2.检测逻辑

`uid_mid`： 字典，key 为uid，mid 为保存的此uid用户发布的最新微博的mid

程序会对UIDS里的uid用户的主页进行访问，获取最新的mid（微博唯一id），与保存好的进行比较，然后进行相应处理

3.发布评论

一开始，是对uids列表执行一次check，需要发表评论的mid放在一个列表里，然后循环一次执行。

后来，觉得这样在uids比较多的时候，会不符合预期，也明显不科学。

所以用了线程池，max_worker=2（两个我觉得就够了）。在每一次对 uid 进行 check 时，一旦有更新的mid ，直接把需要执行的任务丢给线程池执行

4.动态添加删除uid

在Terminal里，输入：`weibo add -u uid_you_want_add -p record_filepath`，会对序列化文件`record`进行修改

-p 参数省略时，请保证 CWD 为 record 文件所在目录，可通过 ` weibo --help ` 查看帮助信息

**Note**： 配置文件config中的UIDS只有在项目第一次运行有效，一旦当前目录下存在序列化文件`record`，将优先从`record`中读取 uids 列表。

并且，因为是在程序运行过程中，对`record`文件进行修改，所以需要对文件加锁（`import fcntl` only worked on Linux )

5.抓包请求

在想要通过Fiddler抓包程序通过requests发出的请求时，会发生出错。

这是因为未设置代理和CA证书导致的，解决办法：

```
    self.ses.proxies = {
        'http': "http://127.0.0.1:8888",
        'https': "http://127.0.0.1:8888",
    }
    self.ses.verify = r'C:\Users\34398\Desktop\FiddlerRoot.pem'
```

PS: Fiddler默认导出的证书为.cer后缀，但是我这必须得转成.pem格式，requests才能正常识别工作（https://www.chinassl.net/ssltools/convert-ssl.html）。



## Todos

* 验证码识别： 通过机器学习识别

* 封禁策略（有时候请求频率过高，会被封IP，返回414.目前是检测到这种情况程序退出）： 防止封禁，或更好的处理策略

* 异常退出邮件通知（本来是想通过supervisor+superlance来实现，由于一些限制原因行不通）：在程序异常退出时，发送邮件通知







