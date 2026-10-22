import {useEffect, useState} from 'react';
import {Check, Circle, RefreshCw, Sparkles, Download, Cpu, ShieldCheck} from 'lucide-react';
import type {Meta, Draft} from './types';
import {api, post, money} from './api';
import {Message, Spinner} from './ui';

type Status = Meta['ai'] & {
  providers: {id:string; name:string; purpose:string; configured:boolean}[];
  training:{version:string;counts:{train:number;validation:number;test:number};scores:Record<string,{test_accuracy:number;test_macro_f1:number}>};
};
export default function AIConnection({onMeta}:{onMeta:(meta:Meta)=>void}) {
  const [status,setStatus] = useState<Status|null>(null);
  const [error,setError] = useState(''), [busy,setBusy] = useState(false);
  const [result,setResult] = useState<Draft|null>(null);
  const [text,setText]=useState('Hôm nay mua nguyên liệu 300 nghìn đồng, trả tiền mặt.');
  const [labels,setLabels]=useState<Record<string,string>>({});
  async function refresh() {
    setBusy(true); setError('');
    try {const [s,m]=await Promise.all([api<Status>('/api/ai/status'),api<Meta>('/api/meta')]);setStatus(s);onMeta(m);setLabels(Object.fromEntries(m.categories.map(c=>[c.id,c.label])));}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  async function test(){
    setBusy(true);setError('');setResult(null);
    try{setResult(await post<Draft>('/api/ai/text',{text}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <section className="card ai-connection" aria-label="AI trên máy">
    <div className="section-title"><h3><Cpu size={17}/> AI trên máy</h3><button aria-label="Làm mới trạng thái AI" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={16}/></button></div>
    <span className="ai-mode enabled"><ShieldCheck size={13}/> Xử lý tại máy · Không cần khóa API</span>
    {status ? <>
      <div className="ai-provider-list">{status.providers.map(p=><div className="ai-provider" key={p.id}>
        <span className={p.configured?'configured':'missing'}>{p.configured?<Check size={17}/>:<Circle size={15}/>}</span>
        <div><strong>{p.name}</strong><small>{p.purpose}</small></div><span className="ai-key-status">{p.configured?'Đã có':'Cần cài'}</span>
      </div>)}</div>
      {(!status.image||!status.voice)&&<Message>Để dùng đủ ảnh và giọng nói, chạy <b>setup-local.bat</b> theo hướng dẫn kèm ZIP. Các chức năng đã sẵn sàng vẫn dùng được.</Message>}
      {status.text&&<div className="ai-live-test">
        <label>Thử mô hình phân loại<textarea rows={3} value={text} onChange={e=>setText(e.target.value)} maxLength={10000}/></label>
        <button className="secondary" onClick={()=>void test()} disabled={busy||!text.trim()}>{busy?<Spinner/>:<Sparkles size={17}/>} Phân tích trên máy</button>
        {result&&<div className="ai-test-result" role="status"><Check size={18}/><div><strong>Đã phân tích · Chưa ghi vào sổ</strong><p>{result.description}</p><p>{result.amount===null?'Cần bổ sung số tiền':money(result.amount)} · {labels[result.category]||result.category}</p>{result.classification?.needs_review&&<small>Mô hình chưa chắc danh mục, cần kiểm tra.</small>}</div></div>}
      </div>}
      {status.training?.scores&&<details className="training-details"><summary>Dữ liệu & kết quả huấn luyện</summary>
        <p>Hai mô hình do nhóm huấn luyện. Dữ liệu mô phỏng, tách theo nhóm câu; chưa đo trên giao dịch thực tế.</p>
        <div className="training-scores">{([['kind','Thu / Chi'],['category','Danh mục']] as const).map(([key,label])=><div key={key}><small>{label}</small><strong>{(status.training.scores[key].test_accuracy*100).toFixed(1)}%</strong><span>Đúng trên tập kiểm tra mô phỏng</span></div>)}</div>
        <p>{status.training.counts.train} câu huấn luyện · {status.training.counts.validation} câu chọn mô hình · {status.training.counts.test} câu kiểm tra.</p>
        <div className="dataset-links">{(['train','validation','test'] as const).map(s=><a key={s} href={'/api/ai/dataset/'+s}><Download size={13}/>{s}.csv</a>)}</div>
        <p>Sửa dữ liệu trong thư mục <b>datasets</b>, chạy <b>train-models.bat</b>, rồi mở lại ứng dụng.</p>
      </details>}
      <p className="footnote">Trạng thái “Đã có” xác nhận thành phần đã được cài. Hãy thử ảnh và bản ghi thực tế để kiểm tra kết quả.</p>
    </> : busy&&<Spinner/>}
    {error&&<Message type="error">{error}</Message>}
  </section>;
}
