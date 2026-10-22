import {useState,useEffect,useCallback} from 'react';
import {Home,ReceiptText,ChartNoAxesCombined,UserRound,Plus,Mic,Camera,PenLine,Bell,ChevronRight,ArrowUpRight,ArrowRight,Download,SlidersHorizontal,Search,ShieldCheck,LogOut,Mail,LockKeyhole,Eye,EyeOff,Sparkles,Leaf,Check,TriangleAlert,CalendarDays,FileSpreadsheet,FileText,ChevronLeft,Trash2,Settings2,Wallet,RefreshCw,Store,MonitorSmartphone} from 'lucide-react';
import type {User,Meta,Report,Transaction,Budget,Period,Scope,EntryMode} from './types';
import {api,post,money,prettyDate,ApiError} from './api';
import {Brand,Message,Spinner,Sheet,PeriodPicker,TransactionRow,Totals,CashChart,ExpenseBreakdown,Empty} from './ui';
import Entry from './Entry';
import AIConnection from './AIConnection';

type Tab='home'|'ledger'|'report'|'settings';
type Overlay='export'|'budgets'|'alerts'|'about'|null;
function PhoneStatusBar(){
  const [time, setTime] = useState(() => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  });
  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      setTime(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`);
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="phone-status-bar" aria-label="Thanh trạng thái điện thoại">
      <span className="phone-time">{time}</span>
      <div className="dynamic-island" title="Dynamic Island & Camera">
        <div className="island-lens" />
      </div>
      <div className="phone-icons" aria-label="Sóng di động, Wi-Fi, Pin">
        <svg className="phone-signal" width="16" height="12" viewBox="0 0 16 12" fill="currentColor">
          <rect x="0" y="9" width="2.5" height="3" rx="0.6"/>
          <rect x="4.5" y="6" width="2.5" height="6" rx="0.6"/>
          <rect x="9" y="3" width="2.5" height="9" rx="0.6"/>
          <rect x="13.5" y="0" width="2.5" height="12" rx="0.6"/>
        </svg>
        <svg className="phone-wifi" width="15" height="12" viewBox="0 0 16 12" fill="currentColor">
          <path d="M8 9.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z" />
          <path d="M4.5 7.2a4.95 4.95 0 0 1 7 0 .8.8 0 0 0 1.13-1.13 6.55 6.55 0 0 0-9.26 0 .8.8 0 0 0 1.13 1.13z" />
          <path d="M1.9 4.6a8.6 8.6 0 0 1 12.2 0 .8.8 0 1 0 1.13-1.13 10.2 10.2 0 0 0-14.46 0 .8.8 0 0 0 1.13 1.13z" />
        </svg>
        <div className="phone-battery" title="Pin 85%">
          <div className="phone-battery-level" />
        </div>
      </div>
    </div>
  );
}

function PhoneHomeIndicator(){
  return (
    <div className="phone-home-indicator" aria-hidden="true">
      <div className="phone-home-bar" />
    </div>
  );
}

export default function App(){
  const [user,setUser]=useState<User|null>(null),[meta,setMeta]=useState<Meta|null>(null),[boot,setBoot]=useState(true),[error,setError]=useState('');
  const [tab,setTab]=useState<Tab>('home'),[period,setPeriod]=useState<Period>('day'),[scope,setScope]=useState<Scope>('business');
  const [report,setReport]=useState<Report|null>(null),[loading,setLoading]=useState(false),[version,setVersion]=useState(0);
  const [range,setRange]=useState<{start:string;end:string}|null>(null),[custom,setCustom]=useState(false);
  const [overlay,setOverlay]=useState<Overlay>(null),[entry,setEntry]=useState<EntryMode|null>(null),[editing,setEditing]=useState<Transaction|null>(null);
  const [toast,setToast]=useState(''),[query,setQuery]=useState(''),[kind,setKind]=useState('all');
  const refresh=()=>setVersion(v=>v+1);
  useEffect(()=>{Promise.all([api<Meta>('/api/meta'),api<User>('/api/auth/me').catch(e=>{if(e.status===401)return null;throw e;})]).then(([m,u])=>{setMeta(m);setUser(u);}).catch(e=>setError(e.message)).finally(()=>setBoot(false));},[]);
  useEffect(()=>{if(!user)return;let cancelled=false;setLoading(true);setError('');const qs=new URLSearchParams({period,scope,...(range||{})});api<Report>('/api/report?'+qs).then(r=>{if(!cancelled)setReport(r);}).catch(e=>{if(!cancelled){setError(e.message);if(e.status===401)setUser(null);}}).finally(()=>{if(!cancelled)setLoading(false);});return()=>{cancelled=true;};},[user,period,scope,range,version]);
  useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(''),3800);return()=>clearTimeout(t);},[toast]);
  const closeEntry=useCallback(()=>{setEntry(null);setEditing(null);},[]);
  const closeOverlay=useCallback(()=>setOverlay(null),[]);
  function navigate(next:Tab){setTab(next);setCustom(false);setRange(null);if(next==='home')setScope('business');if(next==='report'||next==='ledger')setPeriod('month');setQuery('');setKind('all');}
  function choosePeriod(p:Period){setPeriod(p);setRange(null);setCustom(false);}
  const alerts=report?.budgets.filter(b=>b.exceeded)||[];
  const filtered=(report?.transactions||[]).filter(t=>(kind==='all'||t.kind===kind)&&(`${t.description} ${meta?.categories.find(c=>c.id===t.category)?.label}`.toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi'))));
  async function logout(){try{await post('/api/auth/logout',{});setUser(null);setReport(null);setTab('home');setScope('business');setPeriod('day');setRange(null);setOverlay(null);}catch(e){setToast((e as Error).message);}}
  return <main className="demo-stage"><aside className="desktop-story"><Brand/><div className="story-main"><span className="eyebrow"><span/> DÀNH CHO HỘ KINH DOANH NHỎ</span><h1>Tiệm nhỏ.<br/>Tài chính <span>rõ.</span></h1><p>Bớt thời gian ghi chép.<br/>Thêm thời gian cho điều bạn yêu.</p><div className="story-note"><span className="note-icon"><Mic size={22}/></span><div><q>Hôm nay mua nguyên liệu<br/>hết sáu trăm nghìn.</q><span><Sparkles size={13}/> Một câu nói. Một khoản chi.</span></div></div><div className="story-features"><span><Check/> Ghi nhanh, dễ kiểm tra</span><span><Check/> Thu chi rõ ràng mỗi ngày</span><span><Check/> Sổ sách luôn trong tầm tay</span></div></div><div className="story-footer"><MonitorSmartphone size={17}/> Demo giao diện mobile · Chạy trên web</div></aside>
  <div className="device-wrapper">
    <span className="phone-btn phone-btn-action" aria-hidden="true"/>
    <span className="phone-btn phone-btn-vol-up" aria-hidden="true"/>
    <span className="phone-btn phone-btn-vol-down" aria-hidden="true"/>
    <span className="phone-btn phone-btn-power" aria-hidden="true"/>
    <section className="device" aria-label="Ứng dụng Sổ Thu Chi AI">
      <PhoneStatusBar/>
      {boot?<div className="boot"><Spinner/><p>Đang mở sổ của bạn…</p></div>:!meta?<div className="boot"><Message type="error">{error}</Message><button className="primary" onClick={()=>location.reload()}>Thử lại</button></div>:!user?<Login onLogin={u=>{setUser(u);setError('');}}/>:<>
      <header className="app-header"><div>{tab==='home'?<><p>Chào {user.name} <span className="sun">☀</span></p><h2>{user.household}</h2></>:<><p>Sổ Thu Chi AI</p><h2>{{ledger:'Sổ giao dịch',report:'Báo cáo thu chi',settings:'Tiệm của bạn',home:''}[tab]}</h2></>}</div><button className="notification icon-button" onClick={()=>setOverlay('alerts')} aria-label={`Thông báo, ${alerts.length} cảnh báo`}><Bell size={22}/>{alerts.length>0&&<i/>}</button></header>
      <div className="app-scroll" aria-busy={loading}>
      {error&&<Message type="error">{error} <button onClick={refresh}>Thử lại</button></Message>}
      {loading&&!report?<div className="skeleton"><div/><div/><div/></div>:report&&<>
      {tab==='home'&&<><PeriodPicker value={period} onChange={choosePeriod}/><section className="balance-card"><div className="balance-top"><span>Chênh lệch thu − chi</span><Wallet size={19}/></div><strong>{money(report.balance)}</strong><div className="balance-bottom"><span><i/> {prettyDate(report.start)}{report.end!==report.start?' – '+prettyDate(report.end):''}</span><span>Đã ghi nhận</span></div><div className="hero-orbit one"/><div className="hero-orbit two"/></section><Totals report={report}/>
      <div className="section-title"><h3>Ghi nhanh một khoản</h3><span className="tiny-label"><Sparkles size={12}/> AI hỗ trợ</span></div><div className="quick-actions"><button className="voice" onClick={()=>setEntry('voice')}><span><Mic/></span><strong>Giọng nói</strong><small>Nói là ghi</small></button><button onClick={()=>setEntry('image')}><span><Camera/></span><strong>Hình ảnh</strong><small>Chụp hoặc tải</small></button><button onClick={()=>setEntry('manual')}><span><PenLine/></span><strong>Nhập tay</strong><small>Ghi theo ý bạn</small></button></div>
      {alerts.length>0?<button className="alert-teaser" onClick={()=>setOverlay('alerts')}><span className="alert-symbol"><TriangleAlert size={18}/></span><div><strong>{alerts[0].label.split(' / ')[0]} vượt ngưỡng</strong><p>Vượt {money(alerts[0].over)} trong {alerts[0].period==='month'?'tháng':alerts[0].period==='week'?'tuần':'ngày'} này</p></div><ChevronRight size={17}/></button>:<div className="calm-note"><ShieldCheck size={18}/> Các khoản chi đang trong ngưỡng thiết lập.</div>}
      <div className="section-title"><h3>Giao dịch gần đây</h3><button onClick={()=>navigate('ledger')}>Xem tất cả <ChevronRight size={14}/></button></div><div className="transaction-list">{report.transactions.slice(0,4).map(t=><TransactionRow key={t.id} item={t} categories={meta.categories} onClick={()=>{setEditing(t);setEntry('manual');}}/>)}{!report.count&&<Empty>Chạm nút + để ghi khoản đầu tiên trong kỳ này.</Empty>}</div><p className="footnote">Dữ liệu mẫu minh họa · Chênh lệch thu chi không phải lợi nhuận.</p></>}
      {tab==='ledger'&&<><PeriodPicker value={period} onChange={choosePeriod}/><div className="search-box"><Search size={18}/><input aria-label="Tìm giao dịch" placeholder="Tìm nội dung, nhóm thu chi…" value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="ledger-filters"><div className="chips">{[['all','Tất cả'],['income','Tiền thu'],['expense','Tiền chi']].map(([k,v])=><button key={k} className={kind===k?'active':''} onClick={()=>setKind(k)}>{v}</button>)}</div><button className="icon-button" aria-label="Xuất sổ giao dịch" onClick={()=>setOverlay('export')}><Download size={18}/></button></div><div className="scope-filter"><span>{filtered.length} giao dịch</span></div><Totals report={{...report,income:filtered.filter(t=>t.kind==='income').reduce((a,t)=>a+t.amount,0),expense:filtered.filter(t=>t.kind==='expense').reduce((a,t)=>a+t.amount,0)}}/>{filtered.map((t,i)=><div key={t.id}>{(i===0||filtered[i-1].date!==t.date)&&<div className="day-label">{t.date===meta.today?'Hôm nay · ':''}{prettyDate(t.date)}</div>}<TransactionRow item={t} categories={meta.categories} onClick={()=>{setEditing(t);setEntry('manual');}}/></div>)}{!filtered.length&&<Empty>Thử đổi kỳ, bộ lọc hoặc thêm giao dịch mới.</Empty>}</>}
      {tab==='report'&&<><div className="section-title report-toolbar"><span><CalendarDays size={16}/> {prettyDate(report.start)} – {prettyDate(report.end)}</span><button aria-label="Chọn khoảng ngày" onClick={()=>setCustom(!custom)}><SlidersHorizontal size={18}/></button></div><PeriodPicker value={period} onChange={choosePeriod}/>{custom&&<form className="custom-range" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);setRange({start:String(f.get('start')),end:String(f.get('end'))});}}><label>Từ ngày<input name="start" type="date" required defaultValue={report.start}/></label><label>Đến ngày<input name="end" type="date" required defaultValue={report.end}/></label><button className="primary" type="submit">Áp dụng</button></form>}<div className="scope-filter"><span>{report.count} giao dịch</span></div><Totals report={report}/><div className="report-balance"><span>Chênh lệch thu − chi</span><strong>{money(report.balance)}</strong></div><section className="card chart-card"><div className="section-title"><h3>Dòng tiền trong kỳ</h3><div className="chart-legend"><span><i/>Thu</span><span><i/>Chi</span></div></div><CashChart report={report}/></section><section className="card"><div className="section-title"><h3>Tiền đã chi vào đâu?</h3></div><ExpenseBreakdown report={report}/></section><button className="settings-row card" onClick={()=>setOverlay('budgets')}><span className="settings-icon amber"><TriangleAlert size={20}/></span><div><strong>Ngưỡng chi tiêu</strong><p>{alerts.length?`${alerts.length} khoản mục cần chú ý`:'Theo dõi từng khoản chi'}</p></div><ChevronRight size={18}/></button><button className="primary export-main" onClick={()=>setOverlay('export')}><Download size={18}/> Xuất sổ sách</button><p className="footnote">Doanh thu chỉ gồm tiền bán hàng và dịch vụ kinh doanh đã ghi nhận. Chênh lệch thu chi không phải lợi nhuận.</p></>}
      {tab==='settings'&&<Settings user={user} meta={meta} onMeta={setMeta} onUser={setUser} onBudgets={()=>setOverlay('budgets')} onExport={()=>setOverlay('export')} onAbout={()=>setOverlay('about')} onLogout={logout} notify={setToast}/>}
      </>}
      </div><nav className="bottom-nav" aria-label="Điều hướng chính"><button className={tab==='home'?'active':''} onClick={()=>navigate('home')}><Home size={21}/><span>Trang chủ</span></button><button className={tab==='ledger'?'active':''} onClick={()=>navigate('ledger')}><ReceiptText size={21}/><span>Giao dịch</span></button><button className="add-nav" aria-label="Thêm giao dịch" onClick={()=>setEntry('text')}><span><Plus size={27}/></span></button><button className={tab==='report'?'active':''} onClick={()=>navigate('report')}><ChartNoAxesCombined size={21}/><span>Báo cáo</span></button><button className={tab==='settings'?'active':''} onClick={()=>navigate('settings')}><UserRound size={21}/><span>Tài khoản</span></button></nav>
      </>}
      {toast&&<div className="toast" role="status"><Check size={18}/>{toast}</div>}
      {entry&&user&&meta&&<Entry mode={entry} editing={editing} meta={meta} onClose={closeEntry} onSaved={(text)=>{refresh();setToast(text);}}/>}
      {overlay&&user&&meta&&report&&<Sheet title={{export:'Xuất sổ sách',budgets:'Ngưỡng chi tiêu',alerts:'Thông báo',about:'Về bản demo'}[overlay]} subtitle={overlay==='export'?'Chọn dữ liệu, tải về và dùng ngay.':undefined} onClose={closeOverlay}>
      {overlay==='export'&&<ExportForm report={report} notify={setToast} onClose={closeOverlay}/>}
      {overlay==='budgets'&&<BudgetForm meta={meta} budgets={report.budgets} onUpdate={refresh} notify={setToast}/>}
      {overlay==='alerts'&&<><div className="section-title"><h3>{alerts.length} khoản cần chú ý</h3><button onClick={()=>setOverlay('budgets')}>Đổi ngưỡng</button></div>{alerts.length?alerts.map(b=><div className="alert-detail" key={b.id}><TriangleAlert size={22}/><div><h3>{b.label}</h3><p>{prettyDate(b.start)} – {prettyDate(b.end)}</p><dl><div><dt>Đã chi</dt><dd>{money(b.actual)}</dd></div><div><dt>Ngưỡng thiết lập</dt><dd>{money(b.limit)}</dd></div><div><dt>Vượt ngưỡng</dt><dd className="expense">{money(b.over)}</dd></div></dl></div></div>):<div className="empty"><ShieldCheck/><strong>Chưa có khoản vượt ngưỡng</strong><p>Cảnh báo xuất hiện khi tổng chi kinh doanh của khoản mục lớn hơn ngưỡng đã đặt.</p></div>}<Message>Cảnh báo dựa trên ngưỡng bạn thiết lập, giúp bạn kiểm tra lại khoản chi.</Message></>}
      {overlay==='about'&&<div className="about"><Brand/><p>Bản demo hỗ trợ ghi nhận thu chi, gợi ý phân loại, tổng hợp báo cáo và xuất dữ liệu của hộ kinh doanh nhỏ.</p><Message>Bản local: hai mô hình thu/chi và danh mục do nhóm huấn luyện trên dữ liệu mô phỏng. Whisper và Tesseract là mô hình có sẵn, chạy trên máy. Không gửi dữ liệu đến API bên ngoài.</Message><p>Chỉ giao dịch bạn xác nhận mới được ghi vào sổ. Tệp âm thanh không được lưu; ảnh chỉ lưu khi bạn chọn đính kèm.</p><p>Demo local lưu dữ liệu trên máy chạy máy chủ. Tài khoản demo dùng chung, chỉ nên dùng dữ liệu minh họa.</p><div className="tech-tags"><span>React · TypeScript</span><span>Python · FastAPI</span><span>{meta.database}</span></div><small>Phiên bản 2.0 · Local AI · Múi giờ Việt Nam</small></div>}
      </Sheet>}
      <PhoneHomeIndicator/>
    </section>
  </div>
  </main>;
}
function Login({onLogin}:{onLogin:(u:User)=>void}){
  const[tab,setTab]=useState<'login'|'register'>('login');
  // ── Login state ──
  const[email,setEmail]=useState(''),[password,setPassword]=useState(''),[visible,setVisible]=useState(false);
  const[loginBusy,setLoginBusy]=useState(false),[loginErr,setLoginErr]=useState('');
  // ── Register state ──
  const[rName,setRName]=useState(''),[rEmail,setREmail]=useState(''),[rPhone,setRPhone]=useState('');
  const[rPass,setRPass]=useState(''),[rPass2,setRPass2]=useState(''),[rShop,setRShop]=useState('');
  const[rVisible,setRVisible]=useState(false),[rVisible2,setRVisible2]=useState(false);
  const[regBusy,setRegBusy]=useState(false),[regErr,setRegErr]=useState('');

  async function submitLogin(demo=false){
    setLoginBusy(true);setLoginErr('');
    try{onLogin(await post<User>('/api/auth/login',{email:demo?'demo@sothuchi.vn':email.trim(),password:demo?'Demo123!':password}));}
    catch(e){setLoginErr((e as Error).message);}
    finally{setLoginBusy(false);}
  }
  async function submitRegister(e:React.FormEvent){
    e.preventDefault();setRegErr('');
    if(rPass.length < 6){setRegErr('Mật khẩu phải có ít nhất 6 ký tự.');return;}
    if(rPass!==rPass2){setRegErr('Mật khẩu nhập lại chưa khớp.');return;}
    const trimmedEmail = rEmail.trim().toLowerCase();
    const trimmedPhone = rPhone.trim();
    if(!trimmedEmail && !trimmedPhone){setRegErr('Vui lòng nhập số điện thoại hoặc email.');return;}
    setRegBusy(true);
    try{
      onLogin(await post<User>('/api/auth/register',{
        name: rName.trim(),
        email: trimmedEmail || null,
        phone: trimmedPhone || null,
        password: rPass,
        shop_name: rShop.trim() || null
      }));
    }
    catch(e){setRegErr((e as Error).message);}
    finally{setRegBusy(false);}
  }

  return(
    <div className="login-scroll">
      <Brand/>
      <div className="login-art">
        <div className="art-circle"/>
        <div className="art-ledger">
          <div><Leaf size={25}/><span>SỔ CỦA TIỆM</span></div>
          <strong>Mỗi ngày,<br/>rõ ràng hơn.</strong>
          <div className="art-line"/><div className="art-line short"/>
          <span className="art-seal"><Check size={26}/></span>
        </div>
        <span className="art-chip"><ArrowUpRight size={16}/> Hôm nay, nhẹ đầu!</span>
        <span className="art-star">✦</span>
      </div>

      {/* ── Tab switcher ── */}
      <div className="auth-tabs" role="tablist">
        <button id="tab-login" role="tab" aria-selected={tab==='login'} className={tab==='login'?'active':''} onClick={()=>{setTab('login');setLoginErr('');}}>Đăng nhập</button>
        <button id="tab-register" role="tab" aria-selected={tab==='register'} className={tab==='register'?'active':''} onClick={()=>{setTab('register');setRegErr('');}}>Đăng ký</button>
      </div>

      {tab==='login'&&(
        <>
          <h1 id="heading-login">Chào bạn,<br/>mở sổ thôi!</h1>
          <p className="login-description">Quản lý thu chi thật gọn.<br/>Để bạn an tâm chăm chút tiệm nhỏ.</p>
          <form onSubmit={e=>{e.preventDefault();void submitLogin();}}>
            <label>Email hoặc số điện thoại<div className="input-icon"><Mail size={18}/><input id="login-email" type="text" autoComplete="username" required value={email} placeholder="Nhập email hoặc số điện thoại" onChange={e=>setEmail(e.target.value)}/></div></label>
            <label>Mật khẩu<div className="input-icon"><LockKeyhole size={18}/><input id="login-password" type={visible?'text':'password'} autoComplete="current-password" required value={password} placeholder="Nhập mật khẩu" onChange={e=>setPassword(e.target.value)}/><button type="button" className="icon-button" aria-label={visible?'Ẩn mật khẩu':'Hiện mật khẩu'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
            {loginErr&&<Message type="error">{loginErr}</Message>}
            <button id="btn-login-submit" type="submit" className="primary" disabled={loginBusy}>{loginBusy?<Spinner/>:<>Đăng nhập <ArrowRight size={18}/></>}</button>
          </form>
          <div className="or"><span/>hoặc khám phá trước<span/></div>
          <button id="btn-demo" className="secondary" disabled={loginBusy} onClick={()=>submitLogin(true)}><Sparkles size={17}/> Trải nghiệm với dữ liệu mẫu</button>
          <p className="login-footer"><ShieldCheck size={14}/> Chỉ dùng dữ liệu minh họa trong bản demo</p>
          <p className="login-footer" style={{marginTop:'0.6rem',cursor:'pointer',color:'var(--primary)'}} onClick={()=>{setTab('register');setRegErr('');}}>Chưa có tài khoản? <strong>Đăng ký ngay</strong></p>
        </>
      )}

      {tab==='register'&&(
        <>
          <h1 id="heading-register">Tạo tài khoản,<br/>bắt đầu ngay!</h1>
          <p className="login-description">Điền thông tin để mở sổ thu chi riêng cho tiệm của bạn.</p>
          <form id="form-register" onSubmit={submitRegister}>
            <label>Họ và tên *<div className="input-icon"><UserRound size={18}/><input id="reg-name" type="text" required placeholder="Ví dụ: Nguyễn Văn An" value={rName} onChange={e=>setRName(e.target.value)} maxLength={100}/></div></label>
            <label>Số điện thoại<div className="input-icon"><span style={{padding:'0 2px',fontSize:'1.05rem',opacity:.7}}>📱</span><input id="reg-phone" type="tel" placeholder="Ví dụ: 0912 345 678" value={rPhone} onChange={e=>setRPhone(e.target.value)} maxLength={20}/></div><span className="auth-subnote">Dùng để đăng nhập hoặc ghi nhận thông tin tiệm.</span></label>
            <label>Email<div className="input-icon"><Mail size={18}/><input id="reg-email" type="email" autoComplete="email" placeholder="Ví dụ: an@gmail.com" value={rEmail} onChange={e=>setREmail(e.target.value)} maxLength={160}/></div><span className="auth-subnote">Có thể để trống nếu đã nhập số điện thoại.</span></label>
            <label>Tên cửa hàng <span style={{opacity:.6,fontSize:'.85em'}}>(tuỳ chọn)</span><div className="input-icon"><Store size={18}/><input id="reg-shop" type="text" placeholder="Ví dụ: Tiệm Trà An Nhiên" value={rShop} onChange={e=>setRShop(e.target.value)} maxLength={100}/></div></label>
            <label>Mật khẩu *<div className="input-icon"><LockKeyhole size={18}/><input id="reg-password" type={rVisible?'text':'password'} required placeholder="Tối thiểu 6 ký tự" value={rPass} onChange={e=>setRPass(e.target.value)} maxLength={200}/><button type="button" className="icon-button" aria-label={rVisible?'Ẩn mật khẩu':'Hiện mật khẩu'} onClick={()=>setRVisible(!rVisible)}>{rVisible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
            <label>Nhập lại mật khẩu *<div className="input-icon"><LockKeyhole size={18}/><input id="reg-password2" type={rVisible2?'text':'password'} required placeholder="Nhập lại mật khẩu" value={rPass2} onChange={e=>setRPass2(e.target.value)} maxLength={200}/><button type="button" className="icon-button" aria-label={rVisible2?'Ẩn mật khẩu':'Hiện mật khẩu'} onClick={()=>setRVisible2(!rVisible2)}>{rVisible2?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
            {regErr&&<Message type="error">{regErr}</Message>}
            <button id="btn-register-submit" type="submit" className="primary" disabled={regBusy}>{regBusy?<Spinner/>:<>Tạo tài khoản <ArrowRight size={18}/></>}</button>
          </form>
          <p className="login-footer" style={{marginTop:'1.2rem',cursor:'pointer',color:'var(--primary)'}} onClick={()=>{setTab('login');setLoginErr('');}}>Đã có tài khoản? <strong>Đăng nhập</strong></p>
        </>
      )}
    </div>
  );
}
function Settings({user,meta,onMeta,onUser,onBudgets,onExport,onAbout,onLogout,notify}:{user:User;meta:Meta;onMeta:(m:Meta)=>void;onUser:(u:User)=>void;onBudgets:()=>void;onExport:()=>void;onAbout:()=>void;onLogout:()=>void;notify:(s:string)=>void}){const[name,setName]=useState(user.household),[edit,setEdit]=useState(false),[busy,setBusy]=useState(false);async function save(){setBusy(true);try{onUser(await api<User>('/api/settings',{method:'PUT',body:JSON.stringify({household:name})}));setEdit(false);notify('Đã cập nhật tên tiệm.');}catch(e){notify((e as Error).message);}finally{setBusy(false);}}return <><div className="profile-card"><div className="avatar"><Store size={30}/></div><h3>{user.household}</h3><p>{user.email.endsWith('@sothuchi.local') ? (user.phone || 'Tài khoản sổ thu chi') : user.email}</p>{user.phone && !user.email.endsWith('@sothuchi.local') && <span style={{fontSize:11,color:'#73846a',display:'block',marginTop:-8,marginBottom:8}}>SĐT: {user.phone}</span>}<span className="pill"><span/> Chủ hộ kinh doanh</span></div><div className="section-title"><h3>Quản lý tiệm</h3></div><div className="settings-group"><button className="settings-row" onClick={()=>setEdit(!edit)}><span className="settings-icon"><Store size={20}/></span><div><strong>Thông tin cửa hàng</strong><p>Đổi tên hiển thị trên sổ sách</p></div><ChevronRight size={18}/></button>{edit&&<div className="inline-edit"><input aria-label="Tên cửa hàng" value={name} onChange={e=>setName(e.target.value)} maxLength={100}/><button className="primary" onClick={save} disabled={busy}>Lưu</button></div>}<button className="settings-row" onClick={onBudgets}><span className="settings-icon amber"><SlidersHorizontal size={20}/></span><div><strong>Ngưỡng cảnh báo</strong><p>Đặt mức chi theo khoản mục</p></div><ChevronRight size={18}/></button><button className="settings-row" onClick={onExport}><span className="settings-icon blue"><Download size={20}/></span><div><strong>Xuất dữ liệu</strong><p>Excel, CSV và PDF</p></div><ChevronRight size={18}/></button></div><AIConnection onMeta={onMeta}/><div className="section-title"><h3>Ứng dụng</h3></div><div className="settings-group"><button className="settings-row" onClick={onAbout}><span className="settings-icon"><Sparkles size={20}/></span><div><strong>AI chạy trên máy</strong><p>Thông tin xử lý và lưu dữ liệu</p></div><ChevronRight size={18}/></button><button className="settings-row logout" onClick={onLogout}><span className="settings-icon"><LogOut size={20}/></span><div><strong>Đăng xuất</strong></div><ChevronRight size={18}/></button></div><p className="footnote">Sổ Thu Chi AI · Phiên bản 2.0 · Local AI<br/>Ghi chép đơn giản, kinh doanh an tâm.</p></>;}
function ExportForm({report,notify,onClose}:{report:Report;notify:(s:string)=>void;onClose:()=>void}){const[kind,setKind]=useState('all'),[format,setFormat]=useState('xlsx'),[busy,setBusy]=useState(false),[error,setError]=useState('');async function download(){setBusy(true);setError('');try{const q=new URLSearchParams({start:report.start,end:report.end,scope:report.scope,kind,format});const res=await fetch('/api/exports?'+q,{credentials:'same-origin'});if(!res.ok){const e=await res.json();throw new Error(typeof e.detail==='string'?e.detail:'Không xuất được tệp.');}const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`So-${kind==='all'?'thu-chi':'doanh-thu'}-${report.start}-${report.end}.${format}`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);notify('Đã tạo tệp. Kiểm tra thư mục Tải xuống.');onClose();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}return <div className="export-form"><div className="export-period"><CalendarDays size={22}/><div><strong>{prettyDate(report.start)} – {prettyDate(report.end)}</strong><p>Phạm vi: Kinh doanh</p></div></div><label>Nội dung sổ</label><button className={'export-choice '+(kind==='all'?'selected':'')} onClick={()=>setKind('all')}><ReceiptText size={22}/><span><strong>Toàn bộ thu – chi</strong><small>Các giao dịch đã xác nhận trong kỳ</small></span><span className="radio"/></button><button className={'export-choice '+(kind==='revenue'?'selected':'')} onClick={()=>setKind('revenue')}><ChartNoAxesCombined size={22}/><span><strong>Doanh thu bán hàng, dịch vụ</strong><small>Không gồm tiền vay và vốn bổ sung</small></span><span className="radio"/></button><label>Định dạng tệp</label><div className="format-choices">{[['xlsx','Excel'],['csv','CSV'],['pdf','PDF']].map(([k,v])=><button className={format===k?'selected':''} key={k} onClick={()=>setFormat(k)}>{k==='pdf'?<FileText size={23}/>:<FileSpreadsheet size={23}/>}<strong>{v}</strong><small>.{k}</small></button>)}</div><div className="export-summary"><span>{kind==='all'?'Tổng thu trong kỳ':'Doanh thu trong kỳ'}</span><strong>{money(kind==='all'?report.income:report.revenue)}</strong></div><Message>Tệp dùng cùng kỳ với báo cáo. Bộ lọc tìm kiếm ở Sổ giao dịch không áp dụng khi xuất.</Message>{error&&<Message type="error">{error}</Message>}<button className="primary" onClick={download} disabled={busy}>{busy?<Spinner/>:<Download size={18}/>} Tải tệp về</button></div>;}
function BudgetForm({meta,budgets,onUpdate,notify}:{meta:Meta;budgets:Budget[];onUpdate:()=>void;notify:(s:string)=>void}){const[category,setCategory]=useState('materials'),[period,setPeriod]=useState<Period>('month'),[amount,setAmount]=useState('6000000'),[busy,setBusy]=useState(false),[error,setError]=useState('');async function save(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await post('/api/budgets',{category,period,amount:Number(amount)});onUpdate();notify('Đã lưu ngưỡng chi tiêu.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}async function remove(id:string){try{await api('/api/budgets/'+id,{method:'DELETE'});onUpdate();notify('Đã bỏ ngưỡng.');}catch(e){setError((e as Error).message);}}return <div className="budget-form"><Message>Chỉ cảnh báo khi tổng chi kinh doanh <strong>lớn hơn</strong> ngưỡng trong ngày, tuần hoặc tháng hiện tại.</Message>{budgets.map(b=><div className={'budget-card '+(b.exceeded?'over':'')} key={b.id}><div><strong>{b.label}</strong><button className="icon-button" aria-label={'Xóa ngưỡng '+b.label} onClick={()=>remove(b.id)}><Trash2 size={15}/></button></div><p>{money(b.actual)} <span>/ {money(b.limit)} mỗi {{day:'ngày',week:'tuần',month:'tháng'}[b.period]}</span></p><div className="budget-track"><i style={{width:Math.min(100,b.actual/b.limit*100)+'%'}}/></div><button className="text-link" onClick={()=>{setCategory(b.category);setPeriod(b.period);setAmount(String(b.limit));}}>Chỉnh ngưỡng</button></div>)}<form onSubmit={save}><h3>Thiết lập ngưỡng</h3><label>Khoản mục<select value={category} onChange={e=>setCategory(e.target.value)}>{meta.categories.filter(c=>c.kind==='expense').map(c=><option value={c.id} key={c.id}>{c.label}</option>)}</select></label><div className="form-row"><label>Theo kỳ<select value={period} onChange={e=>setPeriod(e.target.value as Period)}><option value="day">Mỗi ngày</option><option value="week">Mỗi tuần</option><option value="month">Mỗi tháng</option></select></label><label>Ngưỡng (VND)<input type="number" min="1" max="1000000000000" step="1" required value={amount} onChange={e=>setAmount(e.target.value)}/></label></div>{error&&<Message type="error">{error}</Message>}<button className="primary" disabled={busy}>{busy?<Spinner/>:<Check size={18}/>} Lưu ngưỡng</button></form></div>;}
