(** Pattern.v: LIKE and REGEXP patterns, their matching semantics, and the
    generalisation lemmas behind rules 7 and 14.

    Characters are compared with an arbitrary function [ceq] supplied by the world,
    so the lemmas hold for case-sensitive and case-insensitive collations alike. *)

From Coq Require Import List Ascii String Bool Arith Lia.
Import ListNotations.

(** ---------------- LIKE ---------------- *)

Inductive ltok : Type := LAny | LOne | LChar (c : ascii).   (* %  _  c *)
Definition lpat := list ltok.

(** [lany m s]: [m] accepts some suffix of [s]. *)
Fixpoint lany (m : list ascii -> bool) (s : list ascii) : bool :=
  m s || match s with [] => false | _ :: s' => lany m s' end.

Section Like.
Variable ceq : ascii -> ascii -> bool.

Fixpoint lmatch (p : lpat) (s : list ascii) : bool :=
  match p with
  | [] => match s with [] => true | _ => false end
  | LAny :: p' => lany (lmatch p') s
  | LOne :: p' => match s with [] => false | _ :: s' => lmatch p' s' end
  | LChar c :: p' => match s with [] => false | x :: s' => ceq c x && lmatch p' s' end
  end.

Lemma lany_mono : forall (m m' : list ascii -> bool) s,
  (forall t, m t = true -> m' t = true) -> lany m s = true -> lany m' s = true.
Proof.
  intros m m' s H. induction s as [|x s IH]; simpl; intro E.
  - rewrite orb_false_r in *. apply H. exact E.
  - apply orb_true_iff in E as [E|E]; apply orb_true_iff; [left; apply H; exact E|right; apply IH; exact E].
Qed.

Lemma lany_here : forall m s, m s = true -> lany m s = true.
Proof. intros m [|x s] H; simpl; rewrite H; reflexivity. Qed.

(** [t] matches at least what [t0] matches. *)
Inductive tle : ltok -> ltok -> Prop :=
  | tle_refl : forall t, tle t t
  | tle_one_any : tle LOne LAny
  | tle_char_one : forall c, tle (LChar c) LOne
  | tle_char_any : forall c, tle (LChar c) LAny.

Lemma lmatch_mono : forall p p', Forall2 tle p p' ->
  forall s, lmatch p s = true -> lmatch p' s = true.
Proof.
  intros p p' H. induction H as [|t t' p p' Ht Hp IH]; intros s E; [exact E|].
  destruct Ht as [[| |c]| |c|c]; simpl in *.
  - eapply lany_mono; [|exact E]. exact IH.
  - destruct s; [discriminate|]. apply IH. exact E.
  - destruct s; [discriminate|]. apply andb_prop in E as [E1 E2]. rewrite E1. apply IH. exact E2.
  - destruct s as [|x s]; [discriminate|]. simpl. apply orb_true_iff. right.
    apply lany_here. apply IH. exact E.
  - destruct s; [discriminate|]. apply andb_prop in E as [_ E]. apply IH. exact E.
  - destruct s as [|x s]; [discriminate|]. apply andb_prop in E as [_ E]. simpl.
    apply orb_true_iff. right. apply lany_here. apply IH. exact E.
Qed.

End Like.

(** Generalisations used by the mutators: every [_] becomes [%]; or one literal
    character becomes [_] (at most the first three positions). *)
Definition all_one_to_any (p : lpat) : lpat :=
  map (fun t => match t with LOne => LAny | _ => t end) p.

Fixpoint char_to_one_at (n : nat) (p : lpat) : lpat :=
  match p, n with
  | [], _ => []
  | LChar _ :: t, 0 => LOne :: t
  | x :: t, 0 => x :: t
  | x :: t, S k => x :: char_to_one_at k t
  end.

Lemma all_one_to_any_gen : forall p, Forall2 tle p (all_one_to_any p).
Proof. induction p as [|[| |c] p IH]; simpl; constructor; try constructor; exact IH. Qed.

Lemma Forall2_refl_tle : forall p, Forall2 tle p p.
Proof. induction p; constructor; [constructor|assumption]. Qed.

Lemma char_to_one_at_gen : forall n p, Forall2 tle p (char_to_one_at n p).
Proof.
  induction n as [|n IH]; intros [|[| |c] p]; simpl; repeat constructor;
    try apply Forall2_refl_tle; try apply IH.
Qed.

(** Specialisation (the Down direction): every [%] becomes [_]. *)
Definition all_any_to_one (p : lpat) : lpat :=
  map (fun t => match t with LAny => LOne | _ => t end) p.

Lemma all_any_to_one_spec : forall p, Forall2 tle (all_any_to_one p) p.
Proof. induction p as [|[| |c] p IH]; simpl; constructor; try constructor; exact IH. Qed.

(** ---------------- REGEXP (a fragment) ---------------- *)

Inductive ratom : Type := RChar (c : ascii) | RDot.
Inductive quant : Type := QOne | QOpt | QStar | QPlus.
Record rx : Type := mk_rx { rx_start : bool; rx_end : bool; rx_items : list (ratom * quant) }.

Section Regex.
Variable ceq : ascii -> ascii -> bool.

Definition amatch (a : ratom) (x : ascii) : bool :=
  match a with RChar c => ceq c x | RDot => true end.

(** Zero or more [a], then [m]. *)
Fixpoint lstar (a : ratom) (m : list ascii -> bool) (s : list ascii) : bool :=
  m s || match s with [] => false | x :: s' => amatch a x && lstar a m s' end.

(** [imatch its s]: the items match the whole of [s]. *)
Fixpoint imatch (its : list (ratom * quant)) (s : list ascii) : bool :=
  match its with
  | [] => match s with [] => true | _ => false end
  | (a, q) :: r =>
      match q with
      | QOne => match s with x :: s' => amatch a x && imatch r s' | [] => false end
      | QOpt => imatch r s || match s with x :: s' => amatch a x && imatch r s' | [] => false end
      | QStar => lstar a (imatch r) s
      | QPlus => match s with x :: s' => amatch a x && lstar a (imatch r) s' | [] => false end
      end
  end.

(** A prefix of [s] is matched (the whole of [s] when [e] is set). *)
Fixpoint pmatch (e : bool) (its : list (ratom * quant)) (pre s : list ascii) : bool :=
  (imatch its (rev pre) && (negb e || match s with [] => true | _ => false end)) ||
  match s with [] => false | x :: s' => pmatch e its (x :: pre) s' end.

(** Matched somewhere in [s] (REGEXP searches; ^ anchors at the start). *)
Fixpoint anywhere (e : bool) (its : list (ratom * quant)) (s : list ascii) : bool :=
  pmatch e its [] s || match s with [] => false | _ :: s' => anywhere e its s' end.

Definition rsearch (r : rx) (s : list ascii) : bool :=
  if rx_start r then pmatch (rx_end r) (rx_items r) [] s else anywhere (rx_end r) (rx_items r) s.

Lemma lstar_mono : forall a (m m' : list ascii -> bool) s,
  (forall t, m t = true -> m' t = true) -> lstar a m s = true -> lstar a m' s = true.
Proof.
  intros a m m' s H. induction s as [|x s IH]; simpl; intro E.
  - rewrite orb_false_r in *. apply H. exact E.
  - apply orb_true_iff in E as [E|E]; apply orb_true_iff; [left; apply H; exact E|right].
    apply andb_prop in E as [E1 E2]. rewrite E1. apply IH. exact E2.
Qed.

Lemma lstar_here : forall a m s, m s = true -> lstar a m s = true.
Proof. intros a m [|x s] H; simpl; rewrite H; reflexivity. Qed.

Inductive qle : quant -> quant -> Prop :=
  | qle_refl : forall q, qle q q
  | qle_plus_star : qle QPlus QStar
  | qle_opt_star : qle QOpt QStar.

Definition ile (x y : ratom * quant) : Prop := fst x = fst y /\ qle (snd x) (snd y).

Lemma imatch_mono : forall its its', Forall2 ile its its' ->
  forall s, imatch its s = true -> imatch its' s = true.
Proof.
  intros its its' H. induction H as [|[a q] [a' q'] r r' [Ea Hq] Hr IH]; intros s E; [exact E|].
  simpl in Ea. subst a'. simpl in Hq. destruct Hq as [[| | |]| |]; simpl in *.
  - destruct s; [discriminate|]. apply andb_prop in E as [E1 E2]. rewrite E1. apply IH. exact E2.
  - apply orb_true_iff in E as [E|E]; apply orb_true_iff; [left; apply IH; exact E|right].
    destruct s; [discriminate|]. apply andb_prop in E as [E1 E2]. rewrite E1. apply IH. exact E2.
  - eapply lstar_mono; [|exact E]. exact IH.
  - destruct s; [discriminate|]. apply andb_prop in E as [E1 E2]. rewrite E1.
    eapply lstar_mono; [|exact E2]. exact IH.
  - destruct s as [|x s]; [discriminate|]. apply andb_prop in E as [E1 E2]. simpl.
    apply orb_true_iff. right. rewrite E1. eapply lstar_mono; [|exact E2]. exact IH.
  - apply orb_true_iff in E as [E|E].
    + apply lstar_here. apply IH. exact E.
    + destruct s as [|x s]; [discriminate|]. apply andb_prop in E as [E1 E2]. simpl.
      apply orb_true_iff. right. rewrite E1. apply lstar_here. apply IH. exact E2.
Qed.

Lemma pmatch_mono : forall e e' its its' pre s,
  (e' = true -> e = true) -> Forall2 ile its its' ->
  pmatch e its pre s = true -> pmatch e' its' pre s = true.
Proof.
  intros e e' its its' pre s He Hi. revert pre. induction s as [|x s IH]; intros pre E; simpl in *.
  - rewrite orb_false_r in *. apply andb_prop in E as [E1 _].
    rewrite (imatch_mono _ _ Hi _ E1). destruct e'; reflexivity.
  - apply orb_true_iff in E as [E|E]; apply orb_true_iff; [left|right; apply IH; exact E].
    apply andb_prop in E as [E1 E2]. rewrite (imatch_mono _ _ Hi _ E1). simpl.
    destruct e'; [|reflexivity]. rewrite (He eq_refl) in E2. exact E2.
Qed.

Lemma anywhere_mono : forall e e' its its' s,
  (e' = true -> e = true) -> Forall2 ile its its' ->
  anywhere e its s = true -> anywhere e' its' s = true.
Proof.
  intros e e' its its' s He Hi. induction s as [|x s IH]; intro E; cbn [anywhere] in *.
  - rewrite orb_false_r in *. eapply pmatch_mono; eauto.
  - apply orb_true_iff in E as [E|E]; apply orb_true_iff; [left; eapply pmatch_mono; eauto|right; auto].
Qed.

Lemma pmatch_anywhere : forall e its s, pmatch e its [] s = true -> anywhere e its s = true.
Proof. intros e its [|x s] H; cbn [anywhere]; rewrite H; reflexivity. Qed.

(** [r'] matches every string [r] matches. *)
Definition rgen (r r' : rx) : Prop :=
  (rx_start r' = true -> rx_start r = true) /\ (rx_end r' = true -> rx_end r = true) /\
  Forall2 ile (rx_items r) (rx_items r').

Lemma rsearch_mono : forall r r' s, rgen r r' -> rsearch r s = true -> rsearch r' s = true.
Proof.
  intros [st en its] [st' en' its'] s [Hs [He Hi]]. simpl in *. unfold rsearch. simpl.
  destruct st, st'; intro E.
  - eapply pmatch_mono; eauto.
  - apply pmatch_anywhere. eapply pmatch_mono; eauto.
  - discriminate (Hs eq_refl).
  - eapply anywhere_mono; eauto.
Qed.

End Regex.

Lemma Forall2_refl_ile : forall its, Forall2 ile its its.
Proof. induction its; constructor; [split; [reflexivity|constructor]|assumption]. Qed.

(** Generalisations (rule 14): drop the anchors; or turn every + and ? into *. *)
Definition rx_drop_anchors (r : rx) : rx := mk_rx false false (rx_items r).

Definition star_all (its : list (ratom * quant)) : list (ratom * quant) :=
  map (fun x => match snd x with QPlus | QOpt => (fst x, QStar) | _ => x end) its.

Definition rx_star_all (r : rx) : rx := mk_rx (rx_start r) (rx_end r) (star_all (rx_items r)).

Lemma rx_drop_anchors_gen : forall r, rgen r (rx_drop_anchors r).
Proof. intros r. repeat split; simpl; try discriminate. apply Forall2_refl_ile. Qed.

Lemma star_all_gen : forall its, Forall2 ile its (star_all its).
Proof.
  induction its as [|[a q] its IH]; simpl; constructor; [|exact IH].
  destruct q; split; simpl; constructor.
Qed.

Lemma rx_star_all_gen : forall r, rgen r (rx_star_all r).
Proof. intros r. repeat split; simpl; auto. apply star_all_gen. Qed.

(** Specialisations (the Down direction): add both anchors; or turn every * into +. *)
Definition rx_add_anchors (r : rx) : rx := mk_rx true true (rx_items r).

Definition plus_all (its : list (ratom * quant)) : list (ratom * quant) :=
  map (fun x => match snd x with QStar => (fst x, QPlus) | _ => x end) its.

Definition rx_plus_all (r : rx) : rx := mk_rx (rx_start r) (rx_end r) (plus_all (rx_items r)).

Lemma rx_add_anchors_spec : forall r, rgen (rx_add_anchors r) r.
Proof. intros r. repeat split; simpl; auto. apply Forall2_refl_ile. Qed.

Lemma plus_all_spec : forall its, Forall2 ile (plus_all its) its.
Proof.
  induction its as [|[a q] its IH]; simpl; constructor; [|exact IH].
  destruct q; split; simpl; constructor.
Qed.

Lemma rx_plus_all_spec : forall r, rgen (rx_plus_all r) r.
Proof. intros r. repeat split; simpl; auto. apply plus_all_spec. Qed.
