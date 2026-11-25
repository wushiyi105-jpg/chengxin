# 参与贡献

餐盘照片估热量：模型只说有什么、多少克，热量由本地营养表乘出来。

## 本地跑起来

```bash
git clone https://github.com/wushiyi105-jpg/chengxin.git && cd chengxin
cp .env.example .env      # 填 VISION_API_KEY 和 VISION_BASE_URL

python -m chengxin analyze samples/meal-1.jpg
python -m chengxin serve   # http://127.0.0.1:8771
```

## 跑测试

```bash
python -m unittest discover tests -v
```

单测不依赖真 key：所有模型调用在测试里都换成了假客户端，没配 .env 也能全绿。Windows 终端如果中文乱码，先把环境变量 PYTHONIOENCODING 设成 utf-8。

## 提 PR

1. fork 本仓库，从 main 开一个分支，名字说清要干什么，比如 fix-csv-encoding。
2. 改代码，能顺手补一个测试就补。
3. 本地把上面的测试命令跑一遍，全绿再往下走。
4. 提 PR，写三件事：改了什么、为什么改、本地测试结果。
5. 动到模型调用那一层的，贴一段真实运行输出，比任何描述都省事。

不用写得很正式，说清楚就行。
