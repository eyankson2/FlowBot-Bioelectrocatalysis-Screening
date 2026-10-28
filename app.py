from __future__ import annotations
import json, queue
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from fluidics import *
from biologic_runner import *

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, *, padding=0):
        super().__init__(parent, padding=padding)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.inner.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._fit_width_if_possible)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_width_if_possible(self, event):
        requested = self.inner.winfo_reqwidth()
        self.canvas.itemconfigure(
            self.window_id,
            width=event.width if requested <= event.width else requested,
        )

    def _bind_mousewheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Shift-MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-event.delta / 120), "units")


class App(tk.Tk):
    BG = "#f4f6f8"
    CARD = "#ffffff"
    NAVY = "#17365d"
    BLUE = "#2f6da1"
    MUTED = "#5f6b76"
    GREEN = "#2e7d32"
    RED = "#b3261e"
    AMBER = "#9a6700"

    def _theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(bg=self.BG)
        style.configure(".", font=("Segoe UI", 9), background=self.BG)
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground="#20262d")
        style.configure("Muted.TLabel", background=self.BG, foreground=self.MUTED)
        style.configure("Header.TLabel", background=self.BG, foreground=self.NAVY, font=("Segoe UI", 22, "bold"))
        style.configure("Section.TLabelframe", background=self.BG, relief="solid", borderwidth=1)
        style.configure("Section.TLabelframe.Label", background=self.BG, foreground=self.NAVY, font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 9, "bold"))
        style.configure("Primary.TButton", padding=(14, 8), font=("Segoe UI", 9, "bold"))
        style.configure("Danger.TButton", padding=(14, 8), font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def __init__(self):
        super().__init__()
        self.title("FlowBot - Umbrella Job Screening + Bio-Logic")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1500, max(1120, int(sw * 0.94)))
        height = min(980, max(760, int(sh * 0.90)))
        self.geometry(f"{width}x{height}+20+20")
        self.minsize(1050, 700)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.jobs = []
        self.controller = None
        self._refresh_requested = False
        self.q = queue.Queue()
        self.status = tk.StringVar(value="IDLE")
        self._theme()
        self._build()
        self.after(100, self._tick)

    def log(self, m):
        self.q.put(str(m))

    def request_refresh(self):
        """Worker threads must not access Tkinter widgets directly."""
        self._refresh_requested = True

    def _set_status(self, value):
        value = str(value).strip().upper()
        self.status.set(value)
        color = {
            "IDLE": "#6b7280",
            "RUNNING": self.BLUE,
            "COMPLETE": self.GREEN,
            "STOPPED": self.AMBER,
            "ERROR": self.RED,
        }.get(value, "#6b7280")
        self.status_badge.configure(bg=color)

    def _build(self):
        header = ttk.Frame(self, padding=(14, 12, 14, 6))
        header.pack(fill="x")
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="FlowBot Umbrella Job Screening", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Define all output mixtures and per-channel electrochemistry inside each umbrella job → prepare all solutions → optional cell purge → simultaneous Bio-Logic → clean → next job",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(1, 0))
        self.status_badge = tk.Label(
            header, textvariable=self.status, fg="white", bg="#6b7280",
            font=("Segoe UI", 9, "bold"), padx=14, pady=6,
        )
        self.status_badge.pack(side="right", padx=(12, 0))
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12)

        bottom = ttk.Frame(self, padding=(12, 4, 12, 10))
        bottom.pack(side="bottom", fill="x")
        controls = ttk.Frame(bottom)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="RUN JOB QUEUE", style="Primary.TButton", command=self.run).pack(side="left")
        ttk.Button(controls, text="STOP", style="Danger.TButton", command=self.stop).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Clear Log", command=lambda: self.logtxt.delete("1.0", "end")).pack(side="left", padx=(16, 0))
        ttk.Button(controls, text="Save Config", command=self.save).pack(side="right")
        ttk.Button(controls, text="Load Config", command=self.load).pack(side="right", padx=(0, 8))
        log_frame = ttk.LabelFrame(bottom, text="Run Log", style="Section.TLabelframe", padding=6)
        log_frame.pack(fill="x")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.logtxt = tk.Text(
            log_frame, height=10, wrap="none", font=("Consolas", 9),
            undo=False, background="#fbfcfd", relief="solid", borderwidth=1,
        )
        log_v = ttk.Scrollbar(log_frame, orient="vertical", command=self.logtxt.yview)
        log_h = ttk.Scrollbar(log_frame, orient="horizontal", command=self.logtxt.xview)
        self.logtxt.configure(yscrollcommand=log_v.set, xscrollcommand=log_h.set)
        self.logtxt.grid(row=0, column=0, sticky="nsew")
        log_v.grid(row=0, column=1, sticky="ns")
        log_h.grid(row=1, column=0, sticky="ew")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        setup_host = ttk.Frame(nb)
        panel_host = ttk.Frame(nb)
        nb.add(setup_host, text="1. Hardware + Stocks")
        nb.add(panel_host, text="2. Umbrella Jobs")
        setup_scroll = ScrollableFrame(setup_host)
        setup_scroll.pack(fill="both", expand=True)
        panel_scroll = ScrollableFrame(panel_host)
        panel_scroll.pack(fill="both", expand=True)
        self.setup = setup_scroll.inner
        self.panel = panel_scroll.inner
        self._setup()
        self._panel()

    def _setup(self):
        hw=ttk.LabelFrame(self.setup,text='Hardware Configuration',style='Section.TLabelframe',padding=10);hw.pack(fill='x',padx=10,pady=10)
        self.com=tk.StringVar(value='COM7');self.dev=tk.IntVar(value=0);self.data=tk.StringVar(value=r'C:\BioLogic_OLE_Test');self.templates=tk.StringVar(value=str((Path(__file__).parent/'templates').resolve()));self.sim_fl=tk.BooleanVar(value=True);self.sim_ec=tk.BooleanVar(value=True);self.gas_com=tk.StringVar(value="COM4");self.sim_gas=tk.BooleanVar(value=True)
        for r,(lab,var) in enumerate([('Pump COM',self.com),('Bio-Logic device ID',self.dev),('Data directory',self.data),('Templates directory',self.templates)]):ttk.Label(hw,text=lab).grid(row=r,column=0,sticky='w',pady=3);ttk.Entry(hw,textvariable=var,width=80).grid(row=r,column=1,sticky='ew',pady=3)
        ttk.Checkbutton(hw,text='Simulate fluidics',variable=self.sim_fl).grid(row=4,column=0,sticky='w');ttk.Checkbutton(hw,text='Simulate Bio-Logic',variable=self.sim_ec).grid(row=4,column=1,sticky='w')
        ttk.Label(hw,text='Gas solenoid Arduino COM').grid(row=5,column=0,sticky='w',pady=3)
        ttk.Entry(hw,textvariable=self.gas_com,width=15).grid(row=5,column=1,sticky='w',pady=3)
        ttk.Checkbutton(hw,text='Simulate gas solenoid (no physical purge)',variable=self.sim_gas).grid(row=6,column=0,columnspan=2,sticky='w')
        ttk.Label(hw,text='Gas purging is ONLY through the separate Arduino solenoid. Port 8 is ONLY the air chase after dispensing.',style='Muted.TLabel').grid(row=7,column=0,columnspan=2,sticky='w',pady=(4,0))
        hw.columnconfigure(1,weight=1)
        st=ttk.LabelFrame(self.setup,text='Four Stock Solutions',style='Section.TLabelframe',padding=10);st.pack(fill='x',padx=10,pady=5)
        self.stock_names=[tk.StringVar(value=x) for x in ('Mediator 1','Mediator 2','Buffer','Substrate')];self.stock_ports=[tk.IntVar(value=x) for x in (2,3,4,5)]
        for i in range(4):ttk.Label(st,text=f'Stock {i+1}').grid(row=i,column=0,sticky='w');ttk.Entry(st,textvariable=self.stock_names[i],width=28).grid(row=i,column=1,padx=5,pady=3);ttk.Combobox(st,textvariable=self.stock_ports[i],values=(2,3,4,5,6,11),state='readonly',width=8).grid(row=i,column=2)
        mp=ttk.LabelFrame(self.setup,text='Output → Bio-Logic Channel + Electrode Label',style='Section.TLabelframe',padding=10);mp.pack(fill='x',padx=10,pady=5)
        self.ch={7:tk.IntVar(value=0),9:tk.IntVar(value=1),10:tk.IntVar(value=2)};self.enz={o:tk.StringVar(value=f'Enzyme Output {o}') for o in (7,9,10)}
        for r,o in enumerate((7,9,10)):ttk.Label(mp,text=f'Output {o}').grid(row=r,column=0,padx=5);ttk.Spinbox(mp,from_=0,to=4,textvariable=self.ch[o],width=6).grid(row=r,column=1);ttk.Label(mp,text='OLE-COM ID').grid(row=r,column=2,padx=5);ttk.Entry(mp,textvariable=self.enz[o],width=35).grid(row=r,column=3,padx=5)
        rp=ttk.LabelFrame(self.setup,text='Run Parameters',style='Section.TLabelframe',padding=10);rp.pack(fill='x',padx=10,pady=5)
        self.initial=tk.DoubleVar(value=10);self.purge=tk.DoubleVar(value=30);self.prime=tk.DoubleVar(value=.5);self.flush=tk.IntVar(value=1);self.overnight=tk.BooleanVar(value=False)
        for i,(lab,var) in enumerate([('Initial N2 solenoid saturation (s)',self.initial),('Cell solenoid purge (s)',self.purge),('Line prime (mL)',self.prime),('Syringe flush repeats',self.flush)]):ttk.Label(rp,text=lab).grid(row=0,column=2*i);ttk.Entry(rp,textvariable=var,width=9).grid(row=0,column=2*i+1,padx=(4,15))
        ttk.Checkbutton(rp,text='Overnight fill',variable=self.overnight).grid(row=0,column=8)
        ttk.Label(self.setup,text='Fixed ports: Flush 1 | Stock inputs 2-6,11 | Cells 7,9,10 | Air chase ONLY 8 | Waste 12 | N2: external solenoid').pack(anchor='w',padx=15,pady=10)
    def _panel(self):
        top=ttk.Frame(self.panel);top.pack(fill='x',padx=10,pady=10);ttk.Button(top,text='Add Umbrella Job',style='Primary.TButton',command=lambda:self.job_editor()).pack(side='left');ttk.Button(top,text='Remove Selected',command=self.remove).pack(side='left',padx=8);ttk.Label(top,text='Double-click a job to edit every mixture and Echem parameter.').pack(side='left',padx=15)
        cols=('id','label','purge','o7','o9','o10','state');self.tree=ttk.Treeview(self.panel,columns=cols,show='headings',height=22)
        for c,t,w in [('id','Job',60),('label','Umbrella Job',220),('purge','Cell Purge',90),('o7','Output 7',320),('o9','Output 9',320),('o10','Output 10',320),('state','State',100)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor='w')
        self.tree.pack(fill='both',expand=True,padx=10,pady=5);self.tree.bind('<Double-1>',self._dbl)
    def _stocks(self):
        names=[x.get().strip() for x in self.stock_names];ports=[int(x.get()) for x in self.stock_ports]
        if any(not x for x in names) or len(set(ports))!=4 or any(p not in (2,3,4,5,6,11) for p in ports):raise ValueError('Four named stocks must use distinct input ports from 2,3,4,5,6,11.')
        return names,ports
    def _default_assignment(self,o):return OutputAssignment(o,f'Output {o} solution',{},3.0,'','CV',dict(TECHNIQUES['CV'].defaults))
    def job_editor(self,index=None):
        try:names,ports=self._stocks()
        except Exception as e:messagebox.showerror('Stocks',str(e));return
        old=self.jobs[index] if index is not None else None; d={a.output_port:a for a in old.assignments} if old else {}
        win=tk.Toplevel(self);win.title('Edit Umbrella Job' if old else 'Add Umbrella Job');win.geometry('1200x680');win.transient(self);win.grab_set()
        label=tk.StringVar(value=old.label if old else f'Umbrella Job {len(self.jobs)+1}')
        purge_job=tk.BooleanVar(value=getattr(old,'cell_purge',True) if old else True)
        ttk.Label(win,text='Umbrella job label').pack(anchor='w',padx=12,pady=(10,2))
        ttk.Entry(win,textvariable=label,width=50).pack(anchor='w',padx=12)
        ttk.Checkbutton(win,text='Activate cell purge for this umbrella job',variable=purge_job).pack(anchor='w',padx=12,pady=(6,0))
        holder=ttk.Frame(win);holder.pack(fill='both',expand=True,padx=10,pady=10);rows={}
        for col,o in enumerate((7,9,10)):
            a=d.get(o,self._default_assignment(o)); enabled=tk.BooleanVar(value=o in d if old else True); lf=ttk.LabelFrame(holder,text=f'Output {o}',style='Section.TLabelframe',padding=8);lf.grid(row=0,column=col,sticky='nsew',padx=5);holder.columnconfigure(col,weight=1)
            ttk.Checkbutton(lf,text='Include this output',variable=enabled).pack(anchor='w'); sol=tk.StringVar(value=a.label);vol=tk.DoubleVar(value=a.volume_ml);tech=tk.StringVar(value=a.technique); params=dict(a.echem_params)
            ttk.Label(lf,text='Solution label').pack(anchor='w');ttk.Entry(lf,textvariable=sol).pack(fill='x');ttk.Label(lf,text='Volume (mL)').pack(anchor='w');ttk.Entry(lf,textvariable=vol).pack(fill='x')
            fr=[]
            rev={int(p):f for p,f in a.fractions.items()}
            for i,(n,p) in enumerate(zip(names,ports)):
                v=tk.DoubleVar(value=rev.get(p,1.0 if (not old and i==0) else 0.0));fr.append(v);r=ttk.Frame(lf);r.pack(fill='x',pady=2);ttk.Label(r,text=f'{n} [P{p}]',width=22).pack(side='left');ttk.Entry(r,textvariable=v,width=10).pack(side='right')
            ttk.Label(lf,text='Technique').pack(anchor='w',pady=(8,0));cb=ttk.Combobox(lf,textvariable=tech,values=list(TECHNIQUES),state='readonly');cb.pack(fill='x')
            def edit_params(o=o): self.param_dialog(win, rows, o)
            ttk.Button(lf,text='Edit Echem Parameters',command=edit_params).pack(fill='x',pady=(6,3))
            scan_rates=list(getattr(a,'scan_rates',[]) or []); purge_after=list(getattr(a,'purge_after_scan_rates',[]) or []); inter_purge={'seconds':float(getattr(a,'inter_scan_purge_s',0.0) or 0.0)}
            copy=ttk.Frame(lf);copy.pack(fill='x');ttk.Label(copy,text='Copy Echem from output:').pack(side='left');src=tk.IntVar(value=7 if o!=7 else 9);ttk.Combobox(copy,textvariable=src,values=[x for x in (7,9,10) if x!=o],state='readonly',width=5).pack(side='left',padx=4)
            rows[o]={'enabled':enabled,'sol':sol,'vol':vol,'fr':fr,'tech':tech,'params':params,'src':src,'scan_rates':scan_rates,'purge_after':purge_after,'inter_purge':inter_purge}
            ttk.Button(lf,text='Copy / Transfer',command=lambda o=o:self._copy_params(rows,o)).pack(fill='x',pady=5)
        def saveit():
            try:
                ass=[]
                for o,r in rows.items():
                    if not r['enabled'].get():continue
                    fs=[float(v.get()) for v in r['fr']]
                    if any(x<0 or x>1 for x in fs) or abs(sum(fs)-1)>1e-6:raise ValueError(f'Output {o}: fractions must be 0-1 and sum to 1.000.')
                    if float(r['vol'].get())<=0 or float(r['vol'].get())>5:raise ValueError(f'Output {o}: volume must be >0 and <=5 mL.')
                    mapped={ports[i]:fs[i] for i in range(4) if fs[i]>0}; comp=' + '.join(f'{names[i]} {fs[i]*100:.1f}% [P{ports[i]}]' for i in range(4) if fs[i]>0)
                    tech=r['tech'].get(); defaults=TECHNIQUES[tech].defaults
                    # if technique changed without opening editor, use its defaults
                    p=r['params'] if set(r['params'])==set(defaults) else dict(defaults)
                    rates=list(r['scan_rates']) if tech in ('CV','CVA') else []
                    purge_after=list(r['purge_after']) if tech in ('CV','CVA') else []
                    purge_s=float(r['inter_purge']['seconds']) if tech in ('CV','CVA') else 0.0
                    ass.append(OutputAssignment(o,r['sol'].get().strip() or f'Output {o} solution',mapped,float(r['vol'].get()),comp,tech,dict(p),rates,purge_after,purge_s))
                if not ass:raise ValueError('An umbrella job must include at least one output.')
                job=UmbrellaJob(job_id=index+1 if old else len(self.jobs)+1,label=label.get().strip() or 'Umbrella Job',assignments=ass,cell_purge=bool(purge_job.get()))
                if old:self.jobs[index]=job
                else:self.jobs.append(job)
                self.refresh();win.destroy()
            except Exception as e:messagebox.showerror('Invalid umbrella job',str(e),parent=win)
        ttk.Button(win,text='Save Umbrella Job',style='Primary.TButton',command=saveit).pack(pady=8)
    def param_dialog(self,parent,rows,o):
        r=rows[o]; tech=r['tech'].get(); defaults=TECHNIQUES[tech].defaults
        if set(r['params'])!=set(defaults): r['params'].clear(); r['params'].update(defaults)
        w=tk.Toplevel(parent); w.title(f'Output {o} - {tech} Parameters'); w.transient(parent); w.grab_set()
        outer=ScrollableFrame(w,padding=8); outer.pack(fill='both',expand=True); body=outer.inner
        vars={}
        is_cv=tech in ('CV','CVA')
        multi_existing=is_cv and bool(r['scan_rates'])
        mode=tk.StringVar(value='Multiple' if multi_existing else 'Single')
        row=0
        for k,d in defaults.items():
            ttk.Label(body,text=k).grid(row=row,column=0,sticky='w',pady=2)
            v=tk.StringVar(value=r['params'].get(k,d)); vars[k]=v
            e=ttk.Entry(body,textvariable=v,width=28); e.grid(row=row,column=1,padx=8,pady=2,sticky='ew')
            if is_cv and k=='dE/dt':
                rate_entry=e
            row+=1
        if is_cv:
            box=ttk.LabelFrame(body,text='Scan Rate Mode',style='Section.TLabelframe',padding=10)
            box.grid(row=row,column=0,columnspan=2,sticky='ew',pady=(12,6)); row+=1
            top=ttk.Frame(box); top.pack(fill='x')
            ttk.Radiobutton(top,text='Single',variable=mode,value='Single').pack(side='left')
            ttk.Radiobutton(top,text='Multiple',variable=mode,value='Multiple').pack(side='left',padx=(18,0))
            msg=tk.StringVar(); ttk.Label(box,textvariable=msg,style='Muted.TLabel',wraplength=560).pack(anchor='w',pady=(5,8))
            multi=ttk.Frame(box); multi.pack(fill='both',expand=True)
            ttk.Label(multi,text='Scan rates (mV/s)').pack(anchor='w')
            initial=', '.join(f'{x:g}' for x in r['scan_rates']) if r['scan_rates'] else r['params'].get('dE/dt','100')
            rates_var=tk.StringVar(value=initial); rates_entry=ttk.Entry(multi,textvariable=rates_var); rates_entry.pack(fill='x',pady=(2,6))
            ttk.Label(multi,text='Inter-scan solenoid N2 purge time (s)').pack(anchor='w')
            purge_time=tk.DoubleVar(value=float(r['inter_purge']['seconds'])); purge_entry=ttk.Entry(multi,textvariable=purge_time,width=15); purge_entry.pack(anchor='w',pady=(2,6))
            ttk.Label(multi,text='Choose boundaries to purge').pack(anchor='w')
            choices=ttk.Frame(multi); choices.pack(fill='x',pady=4); boundary_vars=[]
            def parse_rates():
                vals=[]
                for token in rates_var.get().replace(';',',').split(','):
                    token=token.strip()
                    if token:
                        x=float(token)
                        if x<=0: raise ValueError('Every scan rate must be > 0 mV/s.')
                        vals.append(x)
                if not vals: raise ValueError('Enter at least one scan rate.')
                return vals
            def rebuild(show_error=True):
                try: vals=parse_rates()
                except Exception as e:
                    if show_error: messagebox.showerror('Scan rates',str(e),parent=w)
                    return
                for child in choices.winfo_children(): child.destroy()
                boundary_vars.clear(); selected=[float(x) for x in r['purge_after']]
                if len(vals)<2: ttk.Label(choices,text='Only one scan rate: no inter-scan boundary is available.').pack(anchor='w'); return
                for i in range(len(vals)-1):
                    v=tk.BooleanVar(value=any(abs(vals[i]-x)<1e-9 for x in selected)); boundary_vars.append((i,v))
                    ttk.Checkbutton(choices,text=f'Purge after {vals[i]:g} mV/s  →  before {vals[i+1]:g} mV/s',variable=v).pack(anchor='w',pady=2)
            ttk.Button(multi,text='Update Boundary Choices',command=rebuild).pack(anchor='w',pady=(2,5))
            ttk.Label(multi,text='With Multiple selected, dE/dt above is not an extra run. FlowBot copies all other CV/CVA parameters and overrides dE/dt with each scan rate in this list.',wraplength=560).pack(anchor='w',pady=(5,2))
            ttk.Label(multi,text='External solenoid N2 purging occurs only at checked boundaries, after all active channels in that stage finish.',wraplength=560).pack(anchor='w')
            def update_mode(*_):
                multiple=mode.get()=='Multiple'
                rate_entry.configure(state='disabled' if multiple else 'normal')
                state='normal' if multiple else 'disabled'
                rates_entry.configure(state=state); purge_entry.configure(state=state)
                for child in choices.winfo_children():
                    try: child.configure(state=state)
                    except tk.TclError: pass
                msg.set('MULTIPLE: dE/dt is controlled only by the scan-rate list below; the dE/dt field above will not run separately.' if multiple else 'SINGLE: FlowBot runs one CV/CVA using the dE/dt value above.')
            mode.trace_add('write',update_mode); rebuild(False); update_mode()
        def ok():
            try:
                r['params'].clear(); r['params'].update({k:v.get() for k,v in vars.items()})
                if is_cv:
                    if mode.get()=='Multiple':
                        vals=parse_rates(); secs=float(purge_time.get())
                        if secs<0: raise ValueError('Purge time cannot be negative.')
                        if len(boundary_vars)!=max(0,len(vals)-1): raise ValueError('Click Update Boundary Choices after changing the scan-rate list.')
                        selected=[vals[i] for i,v in boundary_vars if v.get()]
                        r['scan_rates'].clear(); r['scan_rates'].extend(vals)
                        r['purge_after'].clear(); r['purge_after'].extend(selected)
                        r['inter_purge']['seconds']=secs
                        r['params']['dE/dt']=f'{vals[0]:g}'
                    else:
                        rate=float(r['params']['dE/dt'])
                        if rate<=0: raise ValueError('dE/dt must be > 0 mV/s.')
                        r['scan_rates'].clear(); r['purge_after'].clear(); r['inter_purge']['seconds']=0.0
                w.destroy()
            except Exception as e: messagebox.showerror('Invalid parameters',str(e),parent=w)
        ttk.Button(body,text='Save Parameters',style='Primary.TButton',command=ok).grid(row=row,column=0,columnspan=2,pady=10)
        body.columnconfigure(1,weight=1)
        w.geometry('700x780')
    def _copy_params(self,rows,dst):
        src=int(rows[dst]['src'].get());rows[dst]['tech'].set(rows[src]['tech'].get());rows[dst]['params'].clear();rows[dst]['params'].update(rows[src]['params']);rows[dst]['scan_rates'].clear();rows[dst]['scan_rates'].extend(rows[src]['scan_rates']);rows[dst]['purge_after'].clear();rows[dst]['purge_after'].extend(rows[src]['purge_after']);rows[dst]['inter_purge']['seconds']=rows[src]['inter_purge']['seconds'];messagebox.showinfo('Copied',f'Echem settings, multi-scan rates, and purge boundaries copied from Output {src} to Output {dst}.')
    def _dbl(self,e):
        row=self.tree.identify_row(e.y)
        if row:self.job_editor(int(row))
    def refresh(self):
        for x in self.tree.get_children():self.tree.delete(x)
        for i,j in enumerate(self.jobs):
            by={a.output_port:a for a in j.assignments}
            def fmt(o):
                if o not in by:return '—'
                a=by[o]; rates=getattr(a,'scan_rates',[]) or []
                sr=(f" | SR: {','.join(f'{x:g}' for x in rates)} mV/s" if a.technique in ('CV','CVA') and rates else '')
                return f"{a.label} | {a.technique}{sr} | {a.composition_text}"
            self.tree.insert('', 'end',iid=str(i),values=(j.job_id,j.label,'ON' if j.cell_purge else 'OFF',fmt(7),fmt(9),fmt(10),j.state.value))
    def remove(self):
        if self.controller and self.controller.running:return
        for i in sorted([int(x) for x in self.tree.selection()],reverse=True):self.jobs.pop(i)
        for i,j in enumerate(self.jobs,1):j.job_id=i
        self.refresh()
    def run(self):
        try:
            if not self.jobs:raise ValueError('Add at least one umbrella job.')
            names,ports=self._stocks(); mapping={o:int(self.ch[o].get()) for o in (7,9,10)}
            if len(set(mapping.values()))!=3:raise ValueError('Outputs 7, 9 and 10 must map to different Bio-Logic channels.')
            enzymes={o:self.enz[o].get().strip() for o in (7,9,10)}
            if self.controller and self.controller.running: raise ValueError('Another run is already in progress.')
            if not self.sim_gas.get() and not self.sim_fl.get() and self.gas_com.get().strip().upper()==self.com.get().strip().upper():
                raise ValueError('Pump and gas Arduino must use DIFFERENT COM ports.')
            logger=EventLogger(self.log,run_log_directory()/f"flowbot_umbrella_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            hw=MediatorFluidicsHardware(MediatorFluidicConfig(com_port=self.com.get().strip()),logger,bool(self.sim_fl.get()))
            gas=SolenoidPurgeSystem(self.gas_com.get().strip(),logger,bool(self.sim_gas.get()))
            runner=BioLogicParallelRunner(BioLogicConfig(device_id=int(self.dev.get()),data_dir=self.data.get(),templates_dir=self.templates.get(),simulate=bool(self.sim_ec.get())),mapping,self.log)
            params=RunParameters(float(self.initial.get()),float(self.purge.get()),float(self.prime.get()),int(self.flush.get()),bool(self.overnight.get()))
            # Stock 4 is the substrate in this workflow; controller uses it for explicit carryover logging.
            self.controller=UmbrellaScreeningController(self.jobs,params,hw,logger,state_callback=self.request_refresh,echem_job_callback=lambda j:runner.run_umbrella_job(j,enzymes,inter_scan_purge_callback=lambda seconds,job_id,requests: gas.purge(seconds,f'Job {job_id} inter-scan N2 purge')),substrate_port=ports[3],gas=gas);self.controller.start();self._set_status('RUNNING');self.log('=== FLOWBOT UMBRELLA JOB QUEUE STARTED ===');self.log(f'Run CSV log: {logger.csv_path}')
        except Exception as e:messagebox.showerror('Could not start',str(e))
    def stop(self):
        if self.controller:self.controller.stop()
    def _tick(self):
        try:
            while True:
                self.logtxt.insert('end', self.q.get_nowait() + '\n')
                self.logtxt.see('end')
        except queue.Empty:
            pass
        if self._refresh_requested:
            self._refresh_requested = False
            self.refresh()
        if self.controller and not self.controller.running:
            self._set_status(self.controller.run_state.value)
            self.refresh()
        self.after(100, self._tick)
    def save(self):
        p=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')]);
        if not p:return
        data={'hardware':{'com':self.com.get(),'dev':self.dev.get(),'data':self.data.get(),'templates':self.templates.get(),'sim_fl':self.sim_fl.get(),'sim_ec':self.sim_ec.get(),'gas_com':self.gas_com.get(),'sim_gas':self.sim_gas.get(),'ch':{str(o):self.ch[o].get() for o in self.ch},'enz':{str(o):self.enz[o].get() for o in self.enz}},'stocks':[{'name':self.stock_names[i].get(),'port':self.stock_ports[i].get()} for i in range(4)],'run':{'initial':self.initial.get(),'purge':self.purge.get(),'prime':self.prime.get(),'flush':self.flush.get(),'overnight':self.overnight.get()},'jobs':[{'job_id':j.job_id,'label':j.label,'cell_purge':j.cell_purge,'assignments':[{'output_port':a.output_port,'label':a.label,'fractions':a.fractions,'volume_ml':a.volume_ml,'composition_text':a.composition_text,'technique':a.technique,'echem_params':a.echem_params,'scan_rates':getattr(a,'scan_rates',[]),'purge_after_scan_rates':getattr(a,'purge_after_scan_rates',[]),'inter_scan_purge_s':getattr(a,'inter_scan_purge_s',0.0)} for a in j.assignments]} for j in self.jobs]}
        Path(p).write_text(json.dumps(data,indent=2),encoding='utf-8');self.log(f'Configuration saved: {p}')
    def load(self):
        p=filedialog.askopenfilename(filetypes=[('JSON','*.json')]);
        if not p:return
        d=json.loads(Path(p).read_text(encoding='utf-8'));h=d['hardware'];self.com.set(h['com']);self.dev.set(h['dev']);self.data.set(h['data']);self.templates.set(h['templates']);self.sim_fl.set(h['sim_fl']);self.sim_ec.set(h['sim_ec']);self.gas_com.set(h.get('gas_com','COM4'));self.sim_gas.set(h.get('sim_gas',True))
        for o in (7,9,10):self.ch[o].set(h['ch'][str(o)]);self.enz[o].set(h['enz'][str(o)])
        for i,s in enumerate(d['stocks']):self.stock_names[i].set(s['name']);self.stock_ports[i].set(s['port'])
        r=d['run'];self.initial.set(r['initial']);self.purge.set(r['purge']);self.prime.set(r['prime']);self.flush.set(r['flush']);self.overnight.set(r['overnight']);self.jobs=[]
        for x in d['jobs']:
            aa=[OutputAssignment(int(a['output_port']),a['label'],{int(k):float(v) for k,v in a['fractions'].items()},float(a['volume_ml']),a.get('composition_text',''),a['technique'],a['echem_params'],[float(v) for v in a.get('scan_rates',[])],[float(v) for v in a.get('purge_after_scan_rates',[])],float(a.get('inter_scan_purge_s',0.0))) for a in x['assignments']];self.jobs.append(UmbrellaJob(job_id=int(x['job_id']),label=x['label'],assignments=aa,cell_purge=bool(x.get('cell_purge',True))))
        self.refresh();self.log(f'Configuration loaded: {p}')
if __name__=='__main__':App().mainloop()
