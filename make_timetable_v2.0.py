from constraint import *
import numpy as np
import json
import itertools

# --------------------------------------------------------------------------
# v2.0
# author: Rex Zhang
# Date : 2019-07-09
# Significant Change: 
# 1. 将课程定义为变量，时间槽定义为值域
# 2. 能够处理固定格式的json文件IO
# 3. 
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 问题定义
# Assumption： 以周为周期排课，即每周的课程安排都一样，不考虑临时调课。
# SuperParameter：
# * 每天课程节数 SLT_DLY: 8
# * 教室数 TTL_ROM：2个
# * 周期内可排天数 TTL_DAY: 2
# User Input:
# * 课程：filename： output.json
# * 可用时间： filename: avail0.son
# * derived parameter：课程数、老师数、学生数、时间槽总数
# * 测试文件：avail0.json较小的可行域, avail1.json几乎全部值域可行
# Output:
# * __目标：为每个课程分配对应的时间槽
# * 输出文件：filename: result.json
# Constraint: 
# 代码即文档
# --------------------------------------------------------------------------

# Course 数据结构为：
# [{
#   'cid' : '33',
#   'tid' : '22',
#   'sid' : ['000001', '000002']
# }]

#------------------------------------------------------------
# 超参数
#------------------------------------------------------------
class SuperParameter :
    SLT_DLY = 8 # 每天最大Timeslot数， 课程节数
    TTL_DAY = 2 # 天数
    TTL_ROM = 2 # 房间数
    @classmethod
    def getAll(self) :
        return SuperParameter.TTL_DAY, SuperParameter.TTL_ROM, SuperParameter.SLT_DLY
class Setting :
    COURSE_FILE = "./output.json"   
    AVAIL_FILE = "./avail1.json"
    OUTPUT_FILE = "./timetable.json"

    TIMEOUT = 60 * 5 # 超过5分钟则视为无解，待实现
    COURSE_TOP  = 50 # 只考虑前多少个课程，可以超过实际最大值
    SOLUTION_TOP = 10 # 需要输出多少个Solution 
   
  
if __name__ == '__main__':
    # 这个Json文件格式和上面的list一样。
    with open(Setting.COURSE_FILE,"r",encoding='utf-8') as f:
        data = json.load(f)
        data = data[:Setting.COURSE_TOP]
        print("-----1.input------", print(len(data)))
        print(data)

    with open(Setting.AVAIL_FILE,"r",encoding='utf-8') as f:
        avail = json.load(f)
    
    # 将老师或学生的id变成key，便于后续查询
    avail_map = {}
    for a in avail :
        avail_map[a["id"]] = a

    # 先找到每堂课可行的时间，即该课程老师和学生可行时间的交集
    c_avail=[]
    for c in data : # 每节课
        tid = c["tid"]
        t_set = set(avail_map[tid]["yes"])
        s_set = set()
        for s in c["sid"] :
            if s in avail_map.keys() : # 如果有avail，则并入可行范围，否则当做该人员任意时间都可以
                s_set = s_set | set(avail_map[s]["yes"])
            
        c_avail.append({
            "cid": c["cid"], 
            "yes": list(t_set & s_set),
        })
    print("-----2.c_avail------", len(c_avail))
    print(c_avail)


    teachers = []
    students = []
    for c in data :
        # for key in c.keys() :
        teachers.append(c['tid'])
        students.extend(c['sid'])
    teachers = list(set(teachers))
    students = list(set(students))

    teachers.sort()
    students.sort()

    # print(teachers, students)


    # 做一个index map方便使用，为了variable下标方便使用
    ind_map_t, ind_map_s, ind_map_c = {}, {}, {}

    for t, i in zip(teachers, range(len(teachers))):
        ind_map_t[t] = i

    for s, i in zip(students, range(len(teachers), len(teachers)+len(students))) :
        ind_map_s[s] = i

    for c, i in zip(data, range(len(data))) :
        ind_map_c[c["cid"]] = i

    # print(ind_map_t, ind_map_s)


    # 通过数组表示课程、学生、老师的关系 
    # 一行代表一节课，6个元素为 a b c x y z, 0、1代表是否出席
    # 根据输入拼凑成一个r_c的模式
    r_c = np.zeros([len(data), len(teachers)+len(students)])

    i = 0
    for c in data :
        t, s   = c['tid'], c['sid']
        # print(i, t, s)
        r_c[i, ind_map_t[t]] = 1
        for s0 in s :
            r_c[i, ind_map_s[s0]] = 1
        i += 1
    print("-----3.r_c------", r_c.shape)
    print(r_c)

    # -----------------------------------------------
    # 开始使用Constraint包创建问题并求解问题
    # -----------------------------------------------
    p = Problem(BacktrackingSolver())
    # p = Problem(MinConflictsSolver())

    #添加决策变量
    #每个变量代表一个课程； 每个变量的值代表一个timeslot
    #变量的数量等于课程数，由于每个课程前面都计算了一个可用时间，因此变量数又等于c_avail的长度
    #
    #变量的值域为0至可安排的Timeslot总数（记为NTS，NTS = 每天最大节数*天数*每天最大教室数；若每天课程节数或每天可用教室数不相等，需要手动计算和规定此参数，v1.0版本暂不考虑这种情况），变量为整数型变量。
    var_cnt = len(c_avail) 
    dmn_min = 0
    dmn_max = SuperParameter.SLT_DLY * SuperParameter.TTL_DAY * SuperParameter.TTL_ROM
    p.addVariables(range(0,var_cnt),range(dmn_min, dmn_max))

    # 添加约束 1
    # 每个课程只可能被安排一次（一个周期内）
    p.addConstraint(AllDifferentConstraint())

    # 添加约束 2
    # 每个课程在该课程yes的时间集合内
    for c in c_avail :
        p.addConstraint(
            InSetConstraint(c["yes"]),
            (ind_map_c[c["cid"]], )
        )

    # 添加约束 3
    # 任意两个课程中，若有相同的老师或学生，则不可安排在同一时间的不同教室，利用r_c表示这个规律
    # 3.-1 前置条件：时间槽的值域由节数、教室数、天数三个因数决定，值域的物理意义是从0开始对时间槽依次编号，编号逻辑是第c节->第r教室->第d天
    #      例如：编号为28的时间槽代表第1天，第1间教室，第4节课（因为28-16=12， 12-8=4）
    # 3.0 遍历 课程的笛卡尔积 得到(c1, c2)
    # 3.1 若c1 和 c2 的差是SLT_DLY的倍数，则表示它们被安排了同一个时间段
    # 3.2 若c1 和 c2 的差不大于SLT_DLY * TTL_ROM，则表示它们被安排在了同一天
   
    
    # 添加约束 4 
    # 若两个课程中有同一个老师或同一个学生，则这两节课不能排在同一天的不同教室中
    # 即： 若r_c中有任一相同的1存在，则这两节课 *不能* 被3.1和3.2逻辑击中。
    for i, j in itertools.product(range(var_cnt), range(var_cnt)) :
        if i >= j : #约束4满足对称性，因此只需设置一遍
            continue
        c1, c2 = data[i], data[j]
        cid1, cid2 = ind_map_c[c1["cid"]], ind_map_c[c2["cid"]]
        if np.any( (r_c[cid1] + r_c[cid2]) > 1) :
            p.addConstraint( 
                # lambda a, b : not ( abs(a - b) % SuperParameter.SLT_DLY == 0 and abs(a - b) < SuperParameter.SLT_DLY * SuperParameter.TTL_ROM ) or print(a-b), 
                lambda a, b : not ( abs(a - b) % SuperParameter.SLT_DLY == 0 and abs(a - b) < SuperParameter.SLT_DLY * SuperParameter.TTL_ROM ), 
                (
                    cid1,
                    cid2,                        
                )
            )

    print("-----4.var------")
    print(p._variables)
    print("-----5.con------")
    print(p._constraints) 

    itr = p.getSolutionIter()

    sol_list = []
    try :
        sol = next(itr)
        for i in range(Setting.SOLUTION_TOP) :
            sol_list.append(sol)
            sol = next(itr)
    except StopIteration as e :
        print(repr(e))

    # 简单可视化下结果

    ret = sol_list #{1: 9, 2: 4, 3: 8, 4: 5, 5: 6, 6: 7, 7: 3} #sol # {1: 7, 2: 4, 3: 5, 4: 0, 5: 6, 6: 3, 7: 1, 8: 2}
    
    print("-----6.sol------")
    result = []
    for r in ret :
        for k in np.sort(list(r.keys())):
            if r[k] == -1 : 
                print('o')
            else :
                val = r[k]

                day = val // ( SuperParameter.SLT_DLY * SuperParameter.TTL_ROM )
                room = (val - day * SuperParameter.SLT_DLY * SuperParameter.TTL_ROM) // SuperParameter.SLT_DLY
                slot = (val - day * SuperParameter.SLT_DLY * SuperParameter.TTL_ROM) %  SuperParameter.SLT_DLY

                result.append({
                    "crsidx": str(k),
                    "agnval": str(val), 
                    "course": data[k],
                    "agnslt": [str(day), str(room), str(slot)],
                    "agntxt": "第{}天,第{}教室,第{}节".format(
                        day,
                        room,
                        slot 
                    )
                })
                print("crs:{}, agnval:{}, agnslt:第{}天,第{}教室,第{}节, crs_dtl:{}"
                    .format(k, r[k],
                     day, room, slot ,
                     data[k]
                ))
        print("==================================================")

    with open(Setting.OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


