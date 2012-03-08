#!/usr/bin/env python
"""
vq: Program to parse output from a HW-module to get statistics
about synchronization issues.

Synchronization is said to be achieved when the difference between the true decoding time
as reported by the HW module and the display refresh rate, for 2 seconds does not
contain any values above 60 ms. This goes for any 2 s period in the clip.
"""

import os
import re
import time
from numpy import *
from pylab import *

# some helper functions
def printheader(word):#{{{1
    """generate a nice header string"""
    print "\n%s\n%s" % (word, '-' * len(word))
#}}}-------------------------------------------------------
def timemsg(s,t):#{{{1
    """time information with 3 decimals"""
    sys.stdout.write("%.3f s" % (round(t, 3)))
    sys.stdout.flush()
#}}}-------------------------------------------------------
class vq:#{{{1
    """Main container class for time measurements"""
    def __init__(self,filename, fps=30):#{{{2
        self.cdelta=[]             # cumuluted delta
        self.dec_time_fps=[]       # dec_time converted to fps
        self.dec_time=[]           # array containing decoding times parsed from the log-file
        self.diff_drr_dec_time=[]  # diff between Display Refresh Rate and dec_time
        self.file_name=None        # name of the file to parse
        self.mov_avg_fps=[]        # mov_avg converted to fps
        self.mov_avg=[]            # array containing moving average
        self.mov_cnt=90            # window size for moving average
        self.num_entries=0         # number of decoding times parsed into dec_time
        self.ok=False              # indicates if file meets requirements or not w.r.t. sync
        self.target_fps=fps        # target fps, defaults to 30
        self.total=0
        self.avg=0
        self.min=0
        self.max=0
        self.minindex=0
        self.maxindex=0
        self.stdfps=0
        self.stdmovfps=0

        # RE for matching decoding time
        self.re=re.compile(".*FrameTime:\s+([0-9]+)\s+ms.*")

        if filename:
            self.file_name=filename
            basename=os.path.basename(self.file_name)
            self.basename=os.path.splitext(basename)[0]
            self.__run("Reading %s" % self.basename, self.__populate)
            self.__calc()
#}}}-------------------------------------------------------
    def __run(self,s,f):#{{{2
        """wrapper for function f to include time measurements"""
        sys.stdout.write(s.ljust(60, '.'))
        t1 = time.clock()
        f()
        t2= time.clock()
        timemsg("", t2-t1)
#}}}-------------------------------------------------------
    def __populate(self):#{{{2
        """fill data structures"""
        self.fp=open(self.file_name, 'r')
        for line in self.fp:
            m=self.re.match(line)
            if m:
                self.dec_time.append(int(m.group(1)))
        self.fp.close()

        self.num_entries = len(self.dec_time)
        if not self.num_entries:
            raise ValueError("Does not contain any timestamps")
#}}}-------------------------------------------------------
    def __calc(self):#{{{2
        """all the clever calculations"""
        # statistics
        #self.__statistics()

        # moving average
        self.__movavg()

        # standard deviation
        #self.__stddev()

        # histogram
        self.__histogram()

        # start width default-case i.e. 30 fps
        # cumulated delta decoding time
        #self.diff_drr_dec_time, self.cdelta=self.__cdelta(self.target_fps)
        self.__cdelta(self.target_fps)
        self.cdelta_orginal=self.cdelta
        self.ok=self.__decision(self.target_fps)

        #lets calculate the fps where sync-target is met.
        for i in range(self.target_fps+20,1,-1):
            self.__cdelta(i)
            tmp=self.__decision(i)
            if tmp:
                break
        sys.stdout.write("\t%s" % self.ok)
        print "\tSync achieved @ %2d fps"%i
#}}}-------------------------------------------------------
    def __statistics(self):#{{{2
        """statistics"""
        self.min=min(self.dec_time)
        self.max=max(self.dec_time)
        self.minindex=self.dec_time.index(self.min)
        self.maxindex=self.dec_time.index(self.max)
        self.total=sum(self.dec_time)
        self.avg=self.total/(self.num_entries+0.0)
#}}}-------------------------------------------------------
    def __movavg(self):#{{{2
        """moving average """
        # calc the moving average, window is self.mov_cnt long
        frac=float(self.mov_cnt)
        first=sum(self.dec_time[0:self.mov_cnt])        # 0..89
        self.mov_avg.append(first/frac)              # mov_avg[0]
        for i in range(self.mov_cnt,self.num_entries):   # 90..len
            second = self.mov_avg[-1] -\
                    self.dec_time[i-self.mov_cnt]/frac +\
                    self.dec_time[i]/frac
            self.mov_avg.append(second)

        # adjust from time in ms to fps
        for a,m in zip(self.dec_time, self.mov_avg):
            self.dec_time_fps.append(1000.0/a)
            self.mov_avg_fps.append(1000.0/m)

        self.avgfps=sum(self.dec_time_fps)/float(len(self.dec_time_fps))
#}}}-------------------------------------------------------
    def __stddev(self):#{{{2
        """standard deviation for framerate and moving average frame rate"""
        # using numpy
        tmp=array(self.dec_time_fps)
        self.stdfps=tmp.std()
        tmp=array(self.mov_avg_fps)
        self.stdmovfps=tmp.std()
#}}}-------------------------------------------------------
    def __cdelta(self,fps):#{{{2
        """cumulated delta """
        self.diff_drr_dec_time=[(1000.0*(1/float(fps)-i/1000.0)) for i in self.dec_time]
        tot=0
        self.cdelta=[]
        for i in self.diff_drr_dec_time: # containing diff between DRR and decoding time
            tot+=i
            if tot>0:
                tot=0
            self.cdelta.append(abs(tot))
        #return diff,cdelta
#}}}-------------------------------------------------------
    def __histogram(self):#{{{2
        """histogram"""
        count={}
        for i in self.dec_time:
            try:
                count[i]+=1
            except KeyError:
                count[i]=1
        self.histogram=zip(count.values(), count.keys())
        self.histogram.sort()
        self.histogram.reverse()
#}}}-------------------------------------------------------
    def __decision(self,fps):#{{{2
        """good or bad
        if cdelta contains values greater than the 60 ms target
        for a period longer than 2 seconds, return False, else True
        """
        ok=True
        target=60
        length=2*fps

        # find all entries larger than target i.e 60 ms or 2*target_fps.
        cnt=0
        cntmax=0
        entries=[]
        for i,v in enumerate(self.cdelta):
            if v>target:
                cnt+=1
            else:
                cnt=0
                continue
            if cnt>cntmax:
                cntmax=cnt
            if cntmax>length:
                ok=False
                break
        return ok
#}}}-------------------------------------------------------
    def showgraph(self):#{{{2
        """graph"""
        #lets make our two arrays movfps and cdelta the same size
        #to have nice aligned plots. Duplicate last value.
        m=len(self.mov_avg_fps)
        c=len(self.cdelta)
        self.dec_time_fps.extend([self.dec_time_fps[-1] for i in range(0,c-m)])
        self.mov_avg_fps.extend([self.mov_avg_fps[-1] for i in range(0,c-m)])

        # change size for figure to 8x8 inches
        rc('figure', figsize=(8,10))
        clf()
        subplot(311)
        plot(self.dec_time_fps, label='fps')
        plot(self.mov_avg_fps, 'r-', label='movfps')
        title(self.file_name)
        ylabel('fps')
        xlabel('frame')
        axhline(y=30, linewidth=2)
        ygridlines = getp(gca(), 'ygridlines')
        xgridlines = getp(gca(), 'xgridlines')
        ygridlines = getp(gca(), 'ygridlines')
        setp(ygridlines, 'linestyle', 'None')
        setp(xgridlines, 'linestyle', '--')
        grid(True)
        legend()

        subplot(312)
        plot(self.cdelta_orginal, label='delta')
        axhline(y=60, linewidth=1, color='r', label='target 60ms')
        ylabel('ms')
        xlabel('frame')
        ygridlines = getp(gca(), 'ygridlines')
        xgridlines = getp(gca(), 'xgridlines')
        ygridlines = getp(gca(), 'ygridlines')
        setp(ygridlines, 'linestyle', 'None')
        setp(xgridlines, 'linestyle', '--')
        grid(True)
        legend()

        subplot(313)
        hist(self.dec_time,100,label='histogram')
        xlabel('decoding time')
        ylabel('count')
        grid(True)
        legend()

        savefig(self.basename + '.png', format='png')
        show()
#}}}-------------------------------------------------------
    def show(self):#{{{2
        """Display data structures"""
        printheader('Statistics')
        print "File name =", self.file_name
        print "Total = %d ms" % (self.total)
        print "Nr entries =", self.num_entries
        print "Average = %f ms" % (self.avg)
        print "Average = %f fps" % (self.avgfps)
        print "Min = %d ms" % (self.min)
        print "Min index =", self.minindex
        print "Max = %d ms" % (self.max)
        print "Max index =", self.maxindex
        print "std dev fps =", self.stdfps
        print "std dev movfps =", self.stdmovfps
#}}}-------------------------------------------------------
#}}}-------------------------------------------------------
def usage(name,msg=""):#{{{1
    if msg != "":
        print msg
    print "Usage: %s [-s][-g] files" % name
    print """\tParses decoder log and warn about sync issues.
    \tmax sync-delay:      60 ms.
    \twindow size:         2  sec.
    \tSamples for mov_avg: 90
    \t-s : show statistics
    \t-g : generate graph
    """
    sys.exit(1)
#}}}-------------------------------------------------------
def main(argv):#{{{1
    import glob,getopt
    argv[0] = os.path.basename(argv[0]) #Remove path from name of script
    showStat=False
    genGraph=False
    sumtrue=[]
    sumfalse=[]
    try:
        opts, args = getopt.getopt(argv[1:],"sg")
    except:
        usage(argv[0],"Non-allowed option")
    for o,a in opts:
        if o == "-s":
            showStat=True
        if o == "-g":
            genGraph=True

    infiles = []
    for a in args:
        infiles.extend(glob.glob(a))
    if len(infiles) < 1:
        usage(argv[0],"No matching file")

    for f in infiles:
        try:
            ave=vq(f)
            if showStat:
                ave.show()
            if genGraph:
                ave.showgraph()
            if ave.ok:
                sumtrue.append(ave.basename)
            else:
                sumfalse.append(ave.basename)
        except ValueError,e:
            print >>sys.stderr, "File %s:" %f,e

    printheader("Summary")
    print "NOK:",len(sumfalse)
    print "OK: ",len(sumtrue)
#}}}-------------------------------------------------------
if __name__ ==  "__main__":#{{{1
    main(sys.argv)
#}}}-------------------------------------------------------
