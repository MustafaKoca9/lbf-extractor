from __future__ import annotations
import datetime, logging, os, platform, re, sys
from dataclasses import dataclass
__version__='1.3.0'
__author__='Mustafa Koca'
__license__='MIT'
__repository__='https://github.com/MustafaKoca9/lbf-extractor'
LOGGER_NAME='lbf_extractor'
ENC_KEY=b'cd562f61-5399-3978-ac76-7c54b0508010'
CHUNK_SIZE=1024*1024
MAX_HEADER_SIZE=20*1024*1024
MIN_HEADER_SIZE=1
TRAILER_SIZE=14
MIN_LOCK_CHECK_SIZE=33
ANSI_RE=re.compile(r'\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])')
class LBFExtractorError(Exception): pass
class SecurityError(LBFExtractorError): pass
class CorruptedArchiveError(LBFExtractorError): pass
@dataclass
class ExtractionStats:
 total_items:int=0
 extracted:int=0
 skipped_null:int=0
 failed:int=0
 missed_blocks:int=0
 missed_failed:int=0
@dataclass
class AuditRecord:
 path:str
 offset:int
 length:int
 reason:str
 is_unmapped:bool=False
class Terminal:
 CYAN='\\033[96m'; GREEN='\\033[92m'; YELLOW='\\033[93m'; RED='\\033[91m'; MAGENTA='\\033[95m'; BOLD='\\033[1m'; DIM='\\033[2m'; RESET='\\033[0m'
 _initialized=False
 @classmethod
 def init(cls):
  if cls._initialized:return
  if platform.system()=='Windows':
   try:os.system('')
   except Exception:pass
  cls._initialized=True
 @classmethod
 def enabled(cls):
  if os.getenv('NO_COLOR'):return False
  try:
   if not sys.stdout.isatty():return False
  except Exception:return False
  cls.init();return True
 @classmethod
 def style(cls,text,*styles):
  if not styles or not cls.enabled():return text
  return ''.join(styles)+text+cls.RESET
 @classmethod
 def clean_len(cls,text):return len(ANSI_RE.sub('',text))
class ColoredFormatter(logging.Formatter):
 LEVEL_MAP={logging.DEBUG:(Terminal.DIM,'DBG'),logging.INFO:(Terminal.CYAN,'INF'),logging.WARNING:(Terminal.YELLOW,'WRN'),logging.ERROR:(Terminal.RED,'ERR'),logging.CRITICAL:(Terminal.RED+Terminal.BOLD,'CRT')}
 def format(self,record):
  color,tag=self.LEVEL_MAP.get(record.levelno,('',record.levelname[:3]))
  ts=datetime.datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
  return f'{Terminal.DIM}[{ts}]{Terminal.RESET} [{Terminal.style(tag,color)}] {record.getMessage()}'
