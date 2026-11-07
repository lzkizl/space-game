"""Fenêtre de discussion avec l'IA.  Usage: python fenetre.py"""
import os
import threading
import tkinter as tk
from tkinter import scrolledtext

import ia


class Fenetre(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Discussion avec l'IA")
        self.geometry("560x640")
        self.configure(bg="#1e1e2e")

        self.historique = scrolledtext.ScrolledText(
            self, wrap="word", state="disabled", bg="#181825", fg="#cdd6f4",
            font=("Segoe UI", 11), relief="flat", padx=10, pady=10)
        self.historique.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.historique.tag_config("toi", foreground="#89b4fa")
        self.historique.tag_config("ia", foreground="#a6e3a1")
        self.historique.tag_config("info", foreground="#6c7086")

        bas = tk.Frame(self, bg="#1e1e2e")
        bas.pack(fill="x", padx=10, pady=(0, 10))
        self.saisie = tk.Entry(bas, font=("Segoe UI", 11), bg="#313244", fg="#cdd6f4",
                               insertbackground="#cdd6f4", relief="flat")
        self.saisie.pack(side="left", fill="x", expand=True, ipady=6)
        self.saisie.bind("<Return>", lambda e: self.envoyer())
        self.bouton = tk.Button(bas, text="Envoyer", command=self.envoyer, bg="#89b4fa", fg="#1e1e2e",
                                relief="flat", font=("Segoe UI", 10, "bold"), padx=14)
        self.bouton.pack(side="right", padx=(8, 0), ipady=3)

        self.model = self.vocab = None
        self.prete = False
        self.afficher("info", "Chargement du modèle…")
        threading.Thread(target=self.charger, daemon=True).start()
        self.saisie.focus()

    def afficher(self, qui, texte):
        self.historique.config(state="normal")
        prefixe = {"toi": "Toi : ", "ia": "IA : ", "info": ""}[qui]
        self.historique.insert("end", prefixe + texte + "\n\n", qui)
        self.historique.config(state="disabled")
        self.historique.see("end")

    def charger(self):
        if not os.path.exists(ia.MODEL_PATH):
            # sans modèle, elle répond quand même aux questions connues (mémoire) et aux calculs
            self.prete = True
            self.after(0, self.afficher, "info", "Pas de modèle entraîné (lance entrainer.bat) : "
                       "je réponds seulement aux questions connues.")
            return
        self.model, self.vocab = ia.charger()
        self.prete = True
        self.after(0, self.afficher, "info", f"IA prête ({len(self.vocab)} mots). Écris un message !")

    def envoyer(self):
        texte = self.saisie.get().strip()
        if not texte or not self.prete:
            return
        self.saisie.delete(0, "end")
        self.afficher("toi", texte)
        self.bouton.config(state="disabled")
        threading.Thread(target=self.penser, args=(texte,), daemon=True).start()

    def penser(self, texte):
        rep = ia.repondre(texte, self.model, self.vocab)
        self.after(0, self.recevoir, rep)

    def recevoir(self, rep):
        self.afficher("ia", rep)
        self.bouton.config(state="normal")
        self.saisie.focus()


if __name__ == "__main__":
    Fenetre().mainloop()
