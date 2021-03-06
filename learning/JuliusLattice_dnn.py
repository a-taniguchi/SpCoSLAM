# encoding: shift_jis
# Akira Taniguchi 2017/01/22-2017/07/06
# 実行すれば、自動的に指定フォルダ内にある音声ファイルを読み込み、Juliusでラティス認識した結果を出力してくれる。
# 注意点：指定フォルダ名があっているか確認すること。
# step:教示回数
# filename:ファイル名
import glob
import codecs
import os
import re
import sys
from __init__ import *

def Makedir(dir):
    try:
        os.mkdir( dir )
    except:
        pass


# juliusに入力するためのwavファイルのリストファイルを作成
def MakeTmpWavListFile( wavfile , trialname):
    Makedir( datafolder + trialname + "/" + "tmp" )
    Makedir( datafolder + trialname + "/" + "tmp/" + trialname )
    fList = codecs.open( datafolder + trialname + "/" + "tmp/" + trialname + "/list.txt" , "w" , "sjis" )
    fList.write( wavfile )
    fList.close()

# Lattice認識
def RecogLattice( wavfile , step , filename , trialname):
    MakeTmpWavListFile( wavfile , trialname )
    if (JuliusVer == "v4.4"):
      binfolder = "bin/linux/julius"
    else:
      binfolder = "bin/julius"
    #print Juliusfolder + "bin/julius -C " + Juliusfolder + "syllable.jconf -C " + Juliusfolder + "am-gmm.jconf -v " + lmfolder + lang_init + " -demo -filelist "+ datafolder + trialname + "/tmp/" + trialname + "/list.txt -confnet -lattice"
    if (step == 0 or step == 1):  #最初は日本語音節のみの単語辞書を使用(step==1が最初)
      p = os.popen( Juliusfolder + binfolder + " -C " + Juliusfolder + "syllable.jconf -C " + Juliusfolder + "am-dnn.jconf -v " + lmfolder + lang_init_DNN + " -demo -filelist "+ datafolder + trialname + "/tmp/" + trialname + "/list.txt -lattice -dnnconf " + Juliusfolder + "julius.dnnconf $*" ) #元設定-n 5 # -gram type -n 5-charconv UTF-8 SJIS -confnet 
      print "Read dic:" ,lang_init_DNN , step
    else:  #更新した単語辞書を使用
      #print Juliusfolder + "bin/julius -C " + Juliusfolder + "syllable.jconf -C " + Juliusfolder + "am-gmm.jconf -v " + datafolder + trialname + "/" + str(step-1) + "/WD.htkdic -demo -filelist tmp/" + trialname + "/list.txt -confnet -lattice"
      p = os.popen( Juliusfolder + binfolder + " -C " + Juliusfolder + "syllable.jconf -C " + Juliusfolder + "am-dnn.jconf -v " + datafolder + trialname + "/" + str(step-1) + "/WD.htkdic -demo -filelist "+ datafolder + trialname + "/tmp/" + trialname + "/list.txt -lattice -dnnconf " + Juliusfolder + "julius.dnnconf $*" ) #元設定-n 5 # -gram type -n 5-charconv UTF-8 SJIS  -confnet
      print "Read dic: " + str(step-1) + "/WD.htkdic" , step
    
    startWordGraphData = False
    wordGraphData = []
    wordData = {}
    index = 1 ###単語IDを1から始める
    line = p.readline()  #一行ごとに読む？
    while line:
        if line.find("end wordgraph data") != -1:
            startWordGraphData = False

        if startWordGraphData==True:
            items = line.split()  #空白で区切る
            wordData = {}
            wordData["range"] = items[1][1:-1].split("..")
            wordData["index"] = str(index)
            index += 1
            for item in items[2:]:
                name,value = item.replace('"','').split("=")   #各name=valueをイコールで区切り格納
                if name in ( "right" , "right_lscore" , "left" ):
                    value = value.split(",")

                wordData[name] = value

            wordGraphData.append(wordData)

        if line.find("begin wordgraph data") != -1:
            startWordGraphData = True
        line = p.readline()
    p.close()
    return wordGraphData

# 認識したlatticeをopenFST形式で保存
def SaveLattice( wordGraphData , filename ):
    f = codecs.open( filename , "w" , "sjis" )
    for wordData in wordGraphData:
        flag = 0
        for r in wordData.get("right" ,[str(len(wordGraphData)), ]):
            l = wordData["index"].decode("sjis")
            w = wordData["name"].decode("sjis")
            
            if int(r) < len(wordGraphData):     #len(wordGraphData)は終端の数字を表す
                s = wordGraphData[int(r)]["AMavg"] #graphcmで良いのか？音響尤度ならばAMavgでは？
                #s = str(float(s) *-1)              #AMavgを使用時のみ(HDecodeの場合と同様の処理？)
                r = str(int(r) + 1)  ###右に繋がっているノードの番号を＋１する                
                #print l,s,w
                #print wordData.get("left","None")
                if ("None" == wordData.get("left","None")) and (flag == 0):
                    l2 = str(0)
                    r2 = l
                    w2 = "<s>"
                    s2 = -1.0
                    f.write( "%s %s %s %s %s\n" % (l2,r2,w2,w2,s2))
                    flag = 1
                    #l = str(0)
                    #print l
                f.write( "%s %s %s %s %s\n" % (l,r,w,w,s) )
            else:
                r = str(int(r) + 1)  ###右に繋がっているノードの番号を＋１する 
                f.write( "%s %s %s %s 1.0\n" % (l,r,w,w) )
    f.write( "%d 0" % int(len(wordGraphData)+1) )
    f.close()

# テキスト形式をバイナリ形式へコンパイル
def FSTCompile( txtfst , syms , outBaseName , filename , trialname ):
    #Makedir( "tmp" )
    #Makedir( "tmp/" + filename )
    os.system( "fstcompile --isymbols=%s --osymbols=%s %s %s.fst" % ( syms , syms , txtfst , outBaseName ) )
    os.system( "fstdraw  --isymbols=%s --osymbols=%s %s.fst > %s/tmp/%s/fst.dot" % ( syms , syms , outBaseName , datafolder + trialname , filename ) )

    # sjisをutf8に変換して，日本語フォントを指定
    #codecs.open( "tmp/" + filename + "/fst_utf.dot" , "w" , "utf-8" ).write( codecs.open( "tmp/" + filename + "/fst.dot" , "r" , "sjis" ).read().replace( 'label' , u'fontname="MS UI Gothic" label' ) )
    # psとして出力
    #os.system( "dot -Tps:cairo tmp/%s/fst_utf.dot > %s.ps" % (filename , outBaseName) )
    # pdf convert
    #os.system( "ps2pdf %s.ps %s.pdf" % (outBaseName, outBaseName) )


def Julius_lattice(step, filename, trialname):
    step = int(step)
    Makedir( filename + "/fst_gmm" )
    Makedir( filename + "/out_gmm" )

    # wavファイルを指定
    files = glob.glob(speech_folder)   #./../../../Julius/directory/CC3Th2/ (相対パス)
    #print files
    files.sort()
    
    #step分までのみ使用
    files2 = [files[i] for i in xrange(step)]

    wordDic = set()
    num = 0

    # 1つづつ認識してFSTフォーマットで保存
    for f in files2:
        txtfstfile = filename + "/fst_gmm/%03d.txt" % num
        print "count...", f , num

        # Lattice認識&保存
        graph = RecogLattice( f, step, filename, trialname )
        SaveLattice( graph , txtfstfile )

        # 単語辞書に追加
        for word in graph:
            wordDic.add( word["name"] )

        num += 1
        
    
    # 単語辞書を作成
    f = codecs.open( filename + "/fst_gmm/isyms.txt" , "w" , "sjis" )
    wordDic = list(wordDic)
    f.write( "<eps>	0\n" )  # latticelmでこの2つは必要らしい
    f.write( "<phi>	1\n" )
    for i in range(len(wordDic)):
        f.write( "%s %d\n" % (wordDic[i].decode("sjis"),i+2) )
    f.close()
    
    # バイナリ形式へコンパイル
    fList = open( filename + "/fst_gmm/fstlist.txt" , "wb" )  # 改行コードがLFでないとダメなのでバイナリ出力で保存
    for i in range(num):
        print "now compile..." , filename + "/fst_gmm/%03d.txt" % i
        
        # FSTコンパイル
        FSTCompile( filename + "/fst_gmm/%03d.txt" % i , filename + "/fst_gmm/isyms.txt" , filename + "/fst_gmm/%03d" % i  ,trialname, trialname)
        
        # lattice lm用のリストファイルを作成
        fList.write( filename + "/fst_gmm/%03d.fst" % i )
        fList.write( "\n" )
    fList.close()
    #print "fstへの変換は、Ubuntuで行ってください"

"""
if __name__ == '__main__':
    #param = sys.argv
    #print param
    param = [0, "test001"]
    Julius_lattice(param[0],param[1])
"""
