# coding: utf-8
from constraint import *
import numpy as np
import json


# # 简单的问题定义
# 
# * 时间段：假设一天有4个TimeSlot
# * 教室：2个
# * 老师：3个
# * 学生：3个
# * 课程：6节
# * __目标：将6节课分到8个时空里(4个ts*2个教室）__

# 课程和学生&老师的关系，其中 abc为老师， xyz为学生
# Course 数据结构为：
# [{
#         cid : {
#                 'tid' : '11',
#                 'sid' : ['000001', '000002',]
#         }
# }]
# 样例：
# [{"33": {"tid": "22", "sid": ["000001", "000002", "000007", "000010", "000020"]}}, {"20": {"tid": "11", "sid": ["000003", "000004", "000009"]}},]

#------------------------------------------------------------
# 超参数
#------------------------------------------------------------
class SuperParameter :
    SLT_DLY = 8 # 每天最大Timeslot数， 课程节数
    TTL_DAY = 3 # 天数
    TTL_ROM = 2 # 房间数
    @classmethod
    def getAll(self) :
        return SuperParameter.TTL_DAY, SuperParameter.TTL_ROM, SuperParameter.SLT_DLY

class TimeAvail : 
    def __init__(self, who, role, yes=[], no=[]):
        self.who = who
        self.role = role
        self.yes = yes
        self.no = no


class UserInput:
    def __init__(self, courses=[], t_avail=[], s_avail=[]):
        self.courses = courses
        self.t_avail = t_avail
        self.s_avail = s_avail
    def __str__(self) :
        return "\n".join([
            str(self.courses), 
            str(self.t_avail), 
            str(self.s_avail),
        ])

if __name__ == '__main__':
    # 这个Json文件格式和上面的list一样。
    with open("output.json","r",encoding='utf-8') as f:
        data = json.load(f)

    with open("avail.json","r",encoding='utf-8') as f:
        avail = json.load(f)
    
    t_avail, s_avail = [], []
    for a in avail : 
        if a["role"] == "teacher" :
            t_avail.append(a)
        elif a["role"] == "student" :
            s_avail.append(a)
        else:
            print("Invalid avail data.")
    
    user_input = UserInput(data, t_avail, s_avail)

    # print(user_input)

    teachers = []
    students = []
    for c in data :
        for key in c.keys() :
            teachers.append(c[key]['tid'])
            students.extend(c[key]['sid'])
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

    # print(ind_map_t, ind_map_s)


    # 通过数组表示课程、学生、老师的关系 
    # 一行代表一节课，6个元素为 a b c x y z, 0、1代表是否出席
    # 根据输入拼凑成一个r_c的模式
    r_c = np.zeros([len(data), len(teachers)+len(students)])

    i = 0
    for c in data :
        for key in c.keys() :
            t, s   = c[key]['tid'], c[key]['sid']
            print(i, t, s)
            r_c[i, ind_map_t[t]] = 1
            for s0 in s :
                r_c[i, ind_map_s[s0]] = 1
        i += 1
    print(r_c)

    # 开始使用Constraint包创建问题并求解问题
    # p = Problem(BacktrackingSolver())
    p = Problem(MinConflictsSolver())

    #添加决策变量
    #每个变量代表一个可安排的Timeslot； 每个变量的值代表每个课程的index；
    #变量的数量等于可安排的Timeslot总数记为NTS（NTS = 每天最大节数*天数*每天最大教室数；若每天课程节数或每天可用教室数不相等，需要手动计算和规定此参数，v1.0版本暂不考虑这种情况）
    #变量的值域为0至总Timeslot数与总课程数中的较大者，变量为整数型变量。
    var_cnt = SuperParameter.SLT_DLY * SuperParameter.TTL_DAY * SuperParameter.TTL_ROM
    dmn_min = -1
    dmn_max = len(data) #max(len(data), SuperParameter.SLT_DLY * SuperParameter.TTL_DAY )
    p.addVariables(range(0,var_cnt),range(dmn_min, dmn_max))

    #添加约束条件：每个时间段只能被分配一个课程
    #当NTS > 课程节数时，大于课程节数的那些assign表示不安排课程。
    # p.addConstraint(AllDifferentConstraint())

    #添加学生和老师可行的时间约束：
    # for t_a in user_input.t_avail :
    #     p.addConstraint(
    #         lambda a : a in t_a["yes"] and a not in t_a["no"],
    #         (ind_map_t[t_a["id"]],)
    #     )
    # #添加学生和老师可行的时间约束：
    # for s_a in user_input.s_avail :
    #     p.addConstraint(
    #         lambda a : a in s_a["yes"] and a not in s_a["no"],
    #         (ind_map_s[s_a["id"]],)
    #     )
    
    # # Timeslot中大于课程数量的值表示不assign。
    flag_unassigned = -1
    # 第d天第r教室第c节课的变量序号为 d*R*C+r*C+c，规定变量从0开始编号
    # 同一天同一Timeslot的不同教室中不能包含 含有相同的老师或学生的课程
    #（举例说明：假设每天8节课，则同一天内第0个Timeslot和第8个Timeslot的课程不能包括同一个老师，因为0和8表示两个不同的教室的第一节课）
    def getVarID(d, r, c, D, R, C) :
        return d * R * C + r * C + c
    D, R, C = SuperParameter.getAll()
    for d in range(D) :
        for c in range(C) :
            for r in range(R-1) :
                # print("----------------------------")
                # print(d, c, r)
                # print("time slot is {}".format(getVarID(d, r, c, D, R, C)))
                p.addConstraint( 
                    lambda a, b: np.all( (r_c[a]+r_c[b]) <= 1 ) if a > flag_unassigned and b > flag_unassigned else True, 
                    (
                        getVarID(d, r, c, D, R, C),
                        getVarID(d, r+1, c, D, R, C),                        
                    )
                )

    # 有效课程的取值只能出现一次：
    # for c in user_input.courses :
    # def course_exist_once(*args) :
    #     print(np.array(args) == 0)
    #     print(sum(np.array(args)==0))
    #     print("--------------------")
    #     return sum( np.array(args) == 0) == 1
    # for idx in range(len(data)) :
    #     print(idx)
    #     p.addConstraint(
    #         # course_exist_once,
    #         lambda *args : np.sum( np.array(args) == idx) == 1 or print('y'),
    #         p._variables
    #     )
    cnt_unassigned = len(p._variables) - len(data)

    sum_pos = sum(range(0, dmn_max))
    sum_neg = 0 - cnt_unassigned 
    sum_con = sum_pos + sum_neg
    # p.addConstraint(MaxSumConstraint(sum_con))
    # p.addConstraint(MinSumConstraint(sum_con))
    # p.addConstraint(ExactSumConstraint(sum_con))
    # p.addConstraint(
    #     lambda *args : np.sum( np.array(args) == -1 ) == cnt_unassigned or print(np.sum( np.array(args) == -1 )),
    #     range(len(p._variables))
    # )
    p.addConstraint(
        # lambda *args : int(sum( args )) == int(sum_con) or print(np.sum( args )) if np.sum(args) < 200 else None,
        lambda *args : int(sum( args )) <= 200 or print(np.sum( args )) if np.sum(args) < 200 else None,
        range(len(p._variables))
    )
    #每天同一节课里，多个教室中的参与者不重复
    # def time_constraint(a,b):
    # ##############################################
    # ##我的课程数现在大于8，这里应该填8吗？
    # ##结果应该是无解，但执行一下貌似内存消耗严重
    # ##############################################
    # #     if a >=6 or b>= 6: #如果被分到6/7，则不安排课程，不检查约束
    # #         return True
    # #     else:
    #     return np.all((r_c[a]+r_c[b])<=1) #相邻的时间里参与者不重复（array两行相加所有元素都<=1)

   
    print(p._variables)
    print(p._constraints)
    itr = [p.getSolution()]

    # itr = p.getSolutionIter()
    i = 0
    sol_list = []
    for it in itr :
        if i > 1 : break
        i += 1
        sol_list.append(it)

    # 简单可视化下结果

    ret = sol_list #{1: 9, 2: 4, 3: 8, 4: 5, 5: 6, 6: 7, 7: 3} #sol # {1: 7, 2: 4, 3: 5, 4: 0, 5: 6, 6: 3, 7: 1, 8: 2}

    for r in ret :
        for k in r.keys():
            if r[k] == -1 : 
                print('o')
            else :
                print("var:{}, crs_idx:{}, crs_dtl:{}".format(k, r[k], data[r[k]]))
        print("==================================================")



