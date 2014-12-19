# coding=utf-8

import os
import sys
import telnetlib
import threading
import time
import calendar
import vt100

reload(sys)
sys.setdefaultencoding('big5')

HOST = "ptt.cc"
USERNAME = 'username'
PASSWORD = '********'

ids = []

Status = {
    'LOGIN': [20, 'guest', 'new'],
    'DOUBLE': [22, u'您想删除其他重复登入的连线吗'],
    'FIRST': [23, u'請按任意鍵繼續'],
    'SECOND': [23, u'您要刪除以上錯誤嘗試的記錄嗎'],
    'MAIN_MENU': [23, u'線上', u'我是' + USERNAME, u'呼叫器'],
    'INDEX': [0, u'【分類看板】'],
    'INDEX2': [0, u'【看板列表】'],
    'INBOARD': [0, u'【板主:'],
    'CLASS': [0, u'【精華文章】'],
    'ARTICLE': [23, u'瀏覽'],
}

MAX = 25 #最大等待次数
MAX_READ = 100 #最大read_some次数

C_I = 24

def contain(s1, s2): 
    return s2 in s1

class Reader(threading.Thread):
    def __init__(self):
        self.tn = telnetlib.Telnet(HOST)
        self.terminal = vt100.VT100()
        self._getData = False
        threading.Thread.__init__(self)
            
    def wait(self, v=1):
        time.sleep(v)
    
    def getData(self):
        s = self.tn.read_very_eager()
        if len(s) > 0:
            self._getData = True
            self.terminal.send(s)
    
    def getLine(self, no):
        return self.terminal.lines[no].tostring().decode('big5', 'ignore')
    
    def getLines(self, start, end):
        ret = ''
        i = start
        while i <= end:
            ret += self.getLine(i) + '\n'
            i += 1
        return ret
    
    def msg(self, s):
        print s
        sys.stdout.flush()
    
    def getStatus(self):
        pass    
    
    def waitStatus(self, status):
        no = Status[status][0]
        i = 0
        while i < MAX:
            i += 1
            self.getData()
            tmp = self.getLine(no)
            ok = True
            for item in Status[status][1:]:
                if not contain(tmp, item):
                    ok = False
                    break
            if ok:
                self.msg('... In ' + status)
                return True
            self.wait()
        return False
    
    def isStatus(self, status):
        no = Status[status][0]
        tmp = self.getLine(no)
        ok = True
        for item in Status[status][1:]:
            if not contain(tmp, item):
                ok = False
                break
        if ok:
            self.msg('... In ' + status)
            return True
        return False
    
    def goMainMenu(self):
        if not self.waitStatus('LOGIN'):
            return False
        
        self.tn.write(USERNAME + '\r')
        self.tn.write(PASSWORD + '\r')
        
        if not self.waitStatus('FIRST'):
            return False
        
        self.tn.write(' ')
        self.wait()
        self.getData()
        
        if self.isStatus('DOUBLE'):
            self.tn.write('y\r')
            self.wait()
            self.getData()

        if self.isStatus('SECOND'):
            self.tn.write('y\r')
            self.wait()
            self.getData()
        
        if self.isStatus('MAIN_MENU'):
            return True
        return False
    
    def sendData(self, s):
        self.tn.write(s)
        self.wait()
        self.getData()
    
    #确保文章翻页
    def sendData2(self, s):
        self.tn.write(s)
        while not self.terminal.lastLineChange():
            self.wait(0.2)
            self.getData()
        self.getData()
    
    #确保光标下移
    def sendDataj(self):
        oldY = self.terminal.y
        self.tn.write('j')
        count = 0
        while oldY == self.terminal.y and count < MAX_READ:
            count += 1
            self.wait(0.2)
            self.getData()
        if count == MAX_READ:
            self.msg('Error: cannot move down')
            return False
        return True
    
    def sendDataAndWait(self, s, status):
        self.tn.write(s)
        count = 0
        
        while (not self.isStatus(status)) and count < MAX:
            if self.isStatus('FIRST'):
                self.tn.write(' ')
            count += 1
            #self.msg('DEBUG: wait status ' + status + ' ' + str(count))
            self.wait(0.2)
            self.getData()
        self.getData()
        if count == MAX_READ:
            self.msg('Error: cannot wait status ' + status)
            return False
        return True
    
    def run(self):
        if not self.goMainMenu():
            return
        
        if not self.sendDataAndWait('C\r', 'INDEX'):
            return False        
        
        if not self.sendDataAndWait('j' * 9 + '\r', 'INDEX2'):
            return False
        
        if not self.sendDataAndWait('j' * 16 + '\r', 'INDEX2'):
            return False        

        
        if not self.sendDataAndWait('j' * 10 + '\r', 'INBOARD'):
            return False
		
        if not self.sendDataAndWait('P' * 2, 'INBOARD'):
            return False
        
        #if not self.sendDataAndWait('z', 'CLASS'):
        #    return False
        self.continueDownDir('ptt/')

        return  
    
    ###down
    def antiAuto(self, line):
        if contain(line, '[Y/n]'):
            self.sendData('n')
    
    def isArticle(self, line):
        if contain(line, '%'):
            return True
        return False
    
    def lastPage(self, line):
        if contain(line, '100%'):
            return True
        return False
    
    def downOneArticle(self):
        ret = ''
        line = ''
        title = ''
        lastline = self.getLine(23)
        if not self.isArticle(lastline):
            return ''
        
        self.terminal.lastLineChange()
        while not self.lastPage(lastline):
            line = self.getLines(0, 22)
            ret += line
            self.sendData2(' ')
            lastline = self.getLine(23)
        
        line2 = self.getLines(0, 22)
        if line != '':
            ls1 = line.splitlines()
            ls2 = line2.splitlines()
            i = 0
            while i < len(ls2):
                if ls1[-1] == ls2[i]:
                    break
                i += 1
            if i != len(ls2):
                line2 = '\n'.join(ls2[i+1:])
            ret += '\n' + line2
        else:
            ret = line2
        
        self.sendDataAndWait('q', 'INBOARD')
        return ret    
        
    def continueDownDir(self, dir):
        if not os.path.isdir(dir):
            os.mkdir(dir)
        self.wait(1)
        for i in range(30):
            title = self.getLine(i%20 + 3)	
            self.msg(title)
            
            #filename = title[1:7].strip() + '.txt'
            #ids.append(title[1:7].strip())
            #f = open(dir + filename, 'w')
			
            self._getData = False
            self.sendData('r')
            if not self._getData:
                self.wait(5)
                self.getData()
                if not self._getData:
                    if not self.sendDataj():
                        break       
                    continue
            
            data = self.downOneArticle()
            
            try:
                t = data.splitlines()[2][9:].strip()
                id = int(calendar.timegm(time.strptime(t, "%b %d %H:%M:%S %Y")))
            except:
                continue
            ids.append(id)
            f = open(dir + str(id) + '.txt', 'w')
            f.write(data.encode('utf-8'))
            f.close()
            if not self.sendDataj():
                break

reader = Reader()
reader.start()
reader.join()
print 'Exit...'
