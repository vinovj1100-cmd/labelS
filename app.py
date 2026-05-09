import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import pandas as pd
import re

class ModernOzonVerifier:
    def __init__(self, root):
        self.root = root
        self.root.title("Ozon Logistics Auditor v5.1 (Pro)")
        self.root.geometry("1200x850")
        self.root.configure(bg="#F8FAFC") # Slate 50
        
        # UI Colors (Tailwind Inspired)
        self.colors = {
            "bg_main": "#F8FAFC",       # Light Slate
            "sidebar": "#0F172A",       # Dark Slate
            "sidebar_hover": "#1E293B",
            "card_bg": "#FFFFFF",
            "text_main": "#1E293B",
            "text_muted": "#64748B",
            "text_light": "#F1F5F9",
            "primary": "#3B82F6",       # Blue
            "primary_hover": "#2563EB",
            "success": "#10B981",       # Emerald
            "success_hover": "#059669",
            "danger": "#EF4444",        # Rose
            "danger_hover": "#DC2626",
            "warning": "#F59E0B",       # Amber
            "warning_hover": "#D97706",
            "border": "#E2E8F0"
        }

        self.style_config()
        self.build_ui()

    def style_config(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Clean up Treeview to look modern
        style.configure("Treeview", 
                        background="#FFFFFF",
                        foreground=self.colors["text_main"],
                        rowheight=35,
                        fieldbackground="#FFFFFF",
                        borderwidth=0,
                        font=("Segoe UI", 10))
        
        style.configure("Treeview.Heading", 
                        font=("Segoe UI", 10, "bold"), 
                        background="#F1F5F9", 
                        foreground=self.colors["text_main"],
                        borderwidth=0,
                        padding=5)
        
        style.map("Treeview", 
                  background=[("selected", "#EFF6FF")], # Light blue selection
                  foreground=[("selected", self.colors["primary"])])
        
        style.configure("TPanedwindow", background=self.colors["bg_main"])

    def create_hover_btn(self, parent, text, bg, hover_bg, fg, command, font, pady=8, padx=15, **kwargs):
        """Custom button factory with hover effects"""
        btn = tk.Button(parent, text=text, bg=bg, fg=fg, command=command, 
                        font=font, relief=tk.FLAT, bd=0, cursor="hand2", pady=pady, padx=padx, **kwargs)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def build_ui(self):
        # --- Sidebar ---
        sidebar = tk.Frame(self.root, bg=self.colors["sidebar"], width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False) # Keep fixed width

        # Logo / Title Area
        title_frame = tk.Frame(sidebar, bg=self.colors["sidebar"], pady=30)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="📦 OZON", font=("Segoe UI", 22, "bold"), bg=self.colors["sidebar"], fg=self.colors["primary"]).pack()
        tk.Label(title_frame, text="AUDITOR PRO", font=("Segoe UI", 12, "bold"), bg=self.colors["sidebar"], fg=self.colors["text_light"]).pack()

        # Status Indicator
        self.status_frame = tk.Frame(sidebar, bg=self.colors["sidebar"], pady=10)
        self.status_frame.pack(fill=tk.X, padx=20, pady=(0, 30))
        self.status_dot = tk.Label(self.status_frame, text="🟢", font=("Segoe UI", 10), bg=self.colors["sidebar"], fg=self.colors["success"])
        self.status_dot.pack(side=tk.LEFT)
        self.status_lbl = tk.Label(self.status_frame, text="System Ready", bg=self.colors["sidebar"], fg=self.colors["text_muted"], font=("Segoe UI", 10))
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        # Action Buttons
        actions_frame = tk.Frame(sidebar, bg=self.colors["sidebar"])
        actions_frame.pack(fill=tk.X, padx=20)

        run_btn = self.create_hover_btn(actions_frame, "⚡ RUN VERIFICATION", 
                                        self.colors["success"], self.colors["success_hover"], "white", 
                                        self.run_analysis, ("Segoe UI", 11, "bold"), pady=12)
        run_btn.pack(fill=tk.X, pady=(0, 15))

        reset_btn = self.create_hover_btn(actions_frame, "🗑 CLEAR ALL DATA", 
                                          self.colors["sidebar_hover"], self.colors["danger"], self.colors["text_light"], 
                                          self.clear_all_inputs, ("Segoe UI", 10))
        reset_btn.pack(fill=tk.X)

        # Help / Info footer
        info_frame = tk.Frame(sidebar, bg=self.colors["sidebar"])
        info_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
        tk.Label(info_frame, text="Supported Delimiters:", bg=self.colors["sidebar"], fg=self.colors["text_muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(info_frame, text="Tabs, Commas, Pipes (|)", bg=self.colors["sidebar"], fg=self.colors["text_muted"], font=("Segoe UI", 9), anchor="w").pack(fill=tk.X)

        # --- Main Content Area ---
        main_content = tk.Frame(self.root, bg=self.colors["bg_main"], padx=30, pady=30)
        main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header Title
        tk.Label(main_content, text="Data Inputs", font=("Segoe UI", 18, "bold"), bg=self.colors["bg_main"], fg=self.colors["text_main"], anchor="w").pack(fill=tk.X, pady=(0, 20))

        # Split Paned Window for Inputs
        paned = ttk.PanedWindow(main_content, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Master
        self.master_area = self.create_input_card(paned, "1. MASTER REFERENCE (Expected)", "Paste database or system export here")
        paned.add(self.master_area, weight=1)

        # Right: Test
        self.test_area = self.create_input_card(paned, "2. SCANNED DATA (Actual)", "Paste scanner output or warehouse data here")
        paned.add(self.test_area, weight=1)

    def create_input_card(self, parent, title, subtitle):
        # Card Container
        card = tk.Frame(parent, bg=self.colors["card_bg"], highlightbackground=self.colors["border"], highlightthickness=1)
        
        # Header Row
        head_row = tk.Frame(card, bg=self.colors["card_bg"])
        head_row.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_lbl = tk.Label(head_row, text=title, font=("Segoe UI", 12, "bold"), bg=self.colors["card_bg"], fg=self.colors["text_main"])
        title_lbl.pack(anchor="w")
        
        sub_lbl = tk.Label(head_row, text=subtitle, font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        sub_lbl.pack(anchor="w")

        # Toolbar
        toolbar = tk.Frame(card, bg=self.colors["card_bg"])
        toolbar.pack(fill=tk.X, padx=20, pady=(0, 10))

        text_widget = scrolledtext.ScrolledText(card, height=15, font=("Consolas", 10), bg="#F8FAFC", fg=self.colors["text_main"], 
                                                relief=tk.FLAT, highlightbackground=self.colors["border"], highlightthickness=1, padx=10, pady=10)

        # Mini Buttons
        btn_font = ("Segoe UI", 9)
        self.create_hover_btn(toolbar, "📋 Paste", self.colors["primary"], self.colors["primary_hover"], "white", 
                              lambda: self.smart_paste(text_widget), btn_font, pady=4, padx=10).pack(side=tk.LEFT, padx=(0, 5))
        
        self.create_hover_btn(toolbar, "📂 Load File", "#E2E8F0", "#CBD5E1", self.colors["text_main"], 
                              lambda: self.load_file(text_widget), btn_font, pady=4, padx=10).pack(side=tk.LEFT, padx=(0, 5))
        
        self.create_hover_btn(toolbar, "❌ Clear", "#FEE2E2", "#FECACA", self.colors["danger"], 
                              lambda: self.clear_single(text_widget), btn_font, pady=4, padx=10).pack(side=tk.RIGHT)

        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        return card

    # --- Controller Methods ---
    def set_status(self, msg, status="ok"):
        self.status_lbl.config(text=msg)
        color = self.colors["success"] if status == "ok" else self.colors["danger"]
        self.status_dot.config(fg=color)

    def smart_paste(self, widget):
        try:
            widget.insert(tk.END, self.root.clipboard_get().strip())
            self.set_status("Data pasted successfully")
        except:
            self.set_status("Clipboard empty", "err")

    def load_file(self, widget):
        path = filedialog.askopenfilename(filetypes=[("Data", "*.csv *.xlsx *.txt")])
        if path:
            try:
                if path.endswith('.xlsx'):
                    df = pd.read_excel(path, header=None)
                    txt = df.to_string(index=False, header=False)
                else:
                    with open(path, 'r', encoding='utf-8') as f:
                        txt = f.read()
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, txt)
                self.set_status(f"Loaded: {path.split('/')[-1]}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def clear_single(self, widget):
        widget.delete("1.0", tk.END)
        self.set_status("Input cleared")

    def clear_all_inputs(self):
        # Access via known structure or store refs better in real app
        # Here we know text widgets are children of the card frames
        for area in [self.master_area, self.test_area]:
            for child in area.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    child.delete("1.0", tk.END)
        self.set_status("All inputs reset")

    # --- Core Logic ---
    def robust_parse(self, text):
        data = {}
        # Regex for flexible splitting (tabs, commas, pipes, spaces)
        splitter = re.compile(r'[,\t|]|\s{2,}')
        
        for line in text.strip().split('\n'):
            clean_line = line.strip()
            if not clean_line: continue
            
            parts = [p.strip() for p in splitter.split(clean_line) if p.strip()]
            if len(parts) >= 1:
                tn = parts[0]
                # If there are more parts, they are items. If not, just tracking number.
                items = set(parts[1:]) if len(parts) > 1 else {"DEFAULT_ITEM"}
                
                if tn in data: data[tn].update(items)
                else: data[tn] = items
        return data

    def run_analysis(self):
        # Extract text from widgets
        def get_text(area):
            for child in area.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    return child.get("1.0", tk.END)
            return ""

        m_txt = get_text(self.master_area)
        t_txt = get_text(self.test_area)

        if len(m_txt) < 5:
            messagebox.showwarning("Missing Data", "Please provide Master Reference data.")
            return

        master = self.robust_parse(m_txt)
        test = self.robust_parse(t_txt)
        
        results = []
        stats = {"match": 0, "err": 0}
        all_tns = sorted(set(master.keys()) | set(test.keys()))

        for tn in all_tns:
            m_set = master.get(tn, set())
            t_set = test.get(tn, set())
            
            missing = m_set - t_set
            extra = t_set - m_set
            
            status = "MATCH"
            if missing or extra or (m_set != t_set):
                status = "ERROR"
                stats["err"] += 1
            else:
                stats["match"] += 1
                
            results.append({
                "tn": tn, "status": status,
                "missing": ", ".join(missing) if missing else "-",
                "extra": ", ".join(extra) if extra else "-"
            })

        self.show_results(results, stats)

    def show_results(self, data, stats):
        win = tk.Toplevel(self.root)
        win.title("Audit Report")
        win.geometry("1000x700")
        win.configure(bg=self.colors["bg_main"])

        # Header Stats
        head = tk.Frame(win, bg="white", pady=20, padx=20)
        head.pack(fill=tk.X)
        
        def card(lbl, val, color):
            f = tk.Frame(head, bg=color, padx=20, pady=10)
            f.pack(side=tk.LEFT, padx=(0, 20))
            tk.Label(f, text=val, font=("Segoe UI", 20, "bold"), bg=color, fg="white").pack()
            tk.Label(f, text=lbl, font=("Segoe UI", 9), bg=color, fg="white").pack()

        card("Total Orders", len(data), self.colors["sidebar"])
        card("Matches", stats["match"], self.colors["success"])
        card("Discrepancies", stats["err"], self.colors["danger"])

        # Table
        tree_frame = tk.Frame(win, bg="white", padx=20, pady=20)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        cols = ("Tracking", "Status", "Missing Items", "Extra Items")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=150 if c == "Tracking" else 100)
            if "Items" in c: tree.column(c, width=300)

        tree.tag_configure("MATCH", background="#DCFCE7") # Light Green
        tree.tag_configure("ERROR", background="#FEE2E2") # Light Red

        for row in data:
            tree.insert("", tk.END, values=(row["tn"], row["status"], row["missing"], row["extra"]), tags=(row["status"],))
            
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Export Btn
        tk.Button(win, text="📥 Export to Excel", 
                  command=lambda: pd.DataFrame(data).to_excel(filedialog.asksaveasfilename(defaultextension=".xlsx"), index=False),
                  bg=self.colors["primary"], fg="white", font=("Segoe UI", 10, "bold"), pady=10).pack(pady=(0, 20))

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernOzonVerifier(root)
    root.mainloop()
