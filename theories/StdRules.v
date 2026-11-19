(** StdRules.v: the standard rules as plug-ins.

    Every rule follows the same recipe:
      1. a root-level rewrite function ([None]/[[]] when the rule does not match),
      2. a theorem: each rewrite is above (Up) or below (Down) its input,
      3. the two packaged with [mk_prule] / [mk_qrule].
    The engine then applies the rule at every admissible position.

    Rule numbers refer to mutation.md.  Rules 5, 12 and 15 (WHERE / ON / HAVING
    cond -> TRUE) and 6, 13, 16 (FALSE -> cond) are not separate plug-ins: they are
    [r_true] and [r_false] applied by the engine at the WHERE / ON position. *)

From Coq Require Import List String Bool.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule.
Local Open Scope string_scope.

(** ---------------- predicate rules ---------------- *)

(** cond -> TRUE (rules 5, 12, 15) *)
Definition f_true (p : pred) : list pred :=
  match p with PTrue => [] | _ => [PTrue] end.

Theorem f_true_sound : forall p p', In p' (f_true p) -> dle p_le Up p p'.
Proof.
  intros p p' H. assert (E : p' = PTrue).
  { destruct p; simpl in H; try contradiction; destruct H as [<-|[]]; reflexivity. }
  subst. apply p_le_true.
Qed.

Definition r_true : prule := mk_prule "cond->TRUE" Up f_true f_true_sound.

(** cond -> FALSE (the Down counterpart; rules 6, 13, 16 read backwards) *)
Definition f_false (p : pred) : list pred :=
  match p with PFalse => [] | _ => [PFalse] end.

Theorem f_false_sound : forall p p', In p' (f_false p) -> dle p_le Down p p'.
Proof.
  intros p p' H. assert (E : p' = PFalse).
  { destruct p; simpl in H; try contradiction; destruct H as [<-|[]]; reflexivity. }
  subst. apply p_le_false.
Qed.

Definition r_false : prule := mk_prule "cond->FALSE" Down f_false f_false_sound.

(** a AND b -> a,  a AND b -> b (rule 11) *)
Definition f_and_drop (p : pred) : list pred :=
  match p with PAnd a b => [a; b] | _ => [] end.

Theorem f_and_drop_sound : forall p p', In p' (f_and_drop p) -> dle p_le Up p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  destruct H as [<-|[<-|[]]]; [apply p_le_and_l|apply p_le_and_r].
Qed.

Definition r_and_drop : prule := mk_prule "AND-drop-operand" Up f_and_drop f_and_drop_sound.

(** a OR b -> a,  a OR b -> b *)
Definition f_or_drop (p : pred) : list pred :=
  match p with POr a b => [a; b] | _ => [] end.

Theorem f_or_drop_sound : forall p p', In p' (f_or_drop p) -> dle p_le Down p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  destruct H as [<-|[<-|[]]]; [apply p_le_or_l|apply p_le_or_r].
Qed.

Definition r_or_drop : prule := mk_prule "OR-drop-operand" Down f_or_drop f_or_drop_sound.

(** Weaken a comparison: < to <=, > to >=, = to <= or >= (rules 8, 9, 10) *)
Definition weaker (c : cmp) : list cmp :=
  match c with
  | CLt => [CLe; CNe] | CGt => [CGe; CNe] | CEq => [CLe; CGe] | _ => []
  end.

Lemma weaker_ok : forall c c', In c' (weaker c) -> cmp_weaker c c'.
Proof.
  intros c c' H. destruct c; simpl in H; try contradiction;
    destruct H as [<-|[<-|[]]]; constructor.
Qed.

Definition f_cmp_weaken (p : pred) : list pred :=
  match p with PCmp c x y => map (fun c' => PCmp c' x y) (weaker c) | _ => [] end.

Theorem f_cmp_weaken_sound : forall p p', In p' (f_cmp_weaken p) -> dle p_le Up p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  apply in_map_iff in H as [c' [<- Hc]]. simpl. apply p_le_cmp. apply weaker_ok. exact Hc.
Qed.

Definition r_cmp_weaken : prule := mk_prule "cmp-weaken" Up f_cmp_weaken f_cmp_weaken_sound.

(** Strengthen a comparison: <= to < or =, >= to > or =, <> to < or > *)
Definition stronger (c : cmp) : list cmp :=
  match c with
  | CLe => [CLt; CEq] | CGe => [CGt; CEq] | CNe => [CLt; CGt] | _ => []
  end.

Lemma stronger_ok : forall c c', In c' (stronger c) -> cmp_weaker c' c.
Proof.
  intros c c' H. destruct c; simpl in H; try contradiction;
    destruct H as [<-|[<-|[]]]; constructor.
Qed.

Definition f_cmp_strengthen (p : pred) : list pred :=
  match p with PCmp c x y => map (fun c' => PCmp c' x y) (stronger c) | _ => [] end.

Theorem f_cmp_strengthen_sound :
  forall p p', In p' (f_cmp_strengthen p) -> dle p_le Down p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  apply in_map_iff in H as [c' [<- Hc]]. simpl. apply p_le_cmp. apply stronger_ok. exact Hc.
Qed.

Definition r_cmp_strengthen : prule :=
  mk_prule "cmp-strengthen" Down f_cmp_strengthen f_cmp_strengthen_sound.

(** LIKE (rule 7): generalise the pattern.  Every [_] becomes [%]; or one literal
    character becomes [_] (each of the first three literal characters). *)
Definition is_one (t : ltok) : bool := match t with LOne => true | _ => false end.
Definition is_any (t : ltok) : bool := match t with LAny => true | _ => false end.

Fixpoint char_positions (i : nat) (p : lpat) : list nat :=
  match p with
  | [] => []
  | LChar _ :: t => i :: char_positions (S i) t
  | _ :: t => char_positions (S i) t
  end.

Definition like_gens (pt : lpat) : list lpat :=
  (if existsb is_one pt then [all_one_to_any pt] else []) ++
  map (fun i => char_to_one_at i pt) (firstn 3 (char_positions 0 pt)).

Lemma like_gens_ok : forall pt pt', In pt' (like_gens pt) -> Forall2 tle pt pt'.
Proof.
  intros pt pt' H. unfold like_gens in H. apply in_app_or in H as [H|H].
  - destruct (existsb is_one pt); simpl in H; [|contradiction].
    destruct H as [<-|[]]. apply all_one_to_any_gen.
  - apply in_map_iff in H as [i [<- _]]. apply char_to_one_at_gen.
Qed.

Definition f_like_up (p : pred) : list pred :=
  match p with PLike e pt => map (PLike e) (like_gens pt) | _ => [] end.

Theorem f_like_up_sound : forall p p', In p' (f_like_up p) -> dle p_le Up p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  apply in_map_iff in H as [pt' [<- Hin]]. simpl. apply p_le_like. apply like_gens_ok. exact Hin.
Qed.

Definition r_like_up : prule := mk_prule "LIKE-generalise" Up f_like_up f_like_up_sound.

(** LIKE, the Down direction: every [%] becomes [_]. *)
Definition f_like_down (p : pred) : list pred :=
  match p with
  | PLike e pt => if existsb is_any pt then [PLike e (all_any_to_one pt)] else []
  | _ => []
  end.

Theorem f_like_down_sound : forall p p', In p' (f_like_down p) -> dle p_le Down p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  destruct (existsb is_any l); simpl in H; [|contradiction].
  destruct H as [<-|[]]. simpl. apply p_le_like. apply all_any_to_one_spec.
Qed.

Definition r_like_down : prule := mk_prule "LIKE-specialise" Down f_like_down f_like_down_sound.

(** REGEXP (rule 14): drop the anchors; or turn every [+] and [?] into [*]. *)
Definition has_q (f : quant -> bool) (r : rx) : bool := existsb (fun x => f (snd x)) (rx_items r).

Definition f_rx_up (p : pred) : list pred :=
  match p with
  | PRegex e r =>
      (if orb (rx_start r) (rx_end r) then [PRegex e (rx_drop_anchors r)] else []) ++
      (if has_q (fun q => match q with QPlus | QOpt => true | _ => false end) r
       then [PRegex e (rx_star_all r)] else [])
  | _ => []
  end.

Theorem f_rx_up_sound : forall p p', In p' (f_rx_up p) -> dle p_le Up p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  apply in_app_or in H as [H|H].
  - destruct (orb (rx_start r) (rx_end r)); simpl in H; [|contradiction].
    destruct H as [<-|[]]. simpl. apply p_le_regex. apply rx_drop_anchors_gen.
  - destruct (has_q _ r); simpl in H; [|contradiction].
    destruct H as [<-|[]]. simpl. apply p_le_regex. apply rx_star_all_gen.
Qed.

Definition r_rx_up : prule := mk_prule "REGEXP-generalise" Up f_rx_up f_rx_up_sound.

(** REGEXP, the Down direction: add both anchors; or turn every [*] into [+]. *)
Definition f_rx_down (p : pred) : list pred :=
  match p with
  | PRegex e r =>
      (if negb (andb (rx_start r) (rx_end r)) then [PRegex e (rx_add_anchors r)] else []) ++
      (if has_q (fun q => match q with QStar => true | _ => false end) r
       then [PRegex e (rx_plus_all r)] else [])
  | _ => []
  end.

Theorem f_rx_down_sound : forall p p', In p' (f_rx_down p) -> dle p_le Down p p'.
Proof.
  intros p p' H. destruct p; simpl in H; try contradiction.
  apply in_app_or in H as [H|H].
  - destruct (negb _); simpl in H; [|contradiction].
    destruct H as [<-|[]]. simpl. apply p_le_regex. apply rx_add_anchors_spec.
  - destruct (has_q _ r); simpl in H; [|contradiction].
    destruct H as [<-|[]]. simpl. apply p_le_regex. apply rx_plus_all_spec.
Qed.

Definition r_rx_down : prule := mk_prule "REGEXP-specialise" Down f_rx_down f_rx_down_sound.

(** ---------------- query rules ---------------- *)

(** SELECT DISTINCT -> SELECT (rule 1) *)
Definition f_distinct_drop (q : query) : list query :=
  match q with QDistinct a => [a] | _ => [] end.

Theorem f_distinct_drop_sound : forall q q', In q' (f_distinct_drop q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_distinct_base.
Qed.

Definition r_distinct_drop : qrule :=
  mk_qrule "DISTINCT-drop" Up f_distinct_drop f_distinct_drop_sound.

(** q -> SELECT DISTINCT q (rule 1 backwards) *)
Definition f_distinct_add (q : query) : list query :=
  match q with QDistinct _ => [] | _ => [QDistinct q] end.

Theorem f_distinct_add_sound : forall q q', In q' (f_distinct_add q) -> dle q_le Down q q'.
Proof.
  intros q q' H. assert (E : q' = QDistinct q).
  { destruct q; simpl in H; try contradiction; destruct H as [<-|[]]; reflexivity. }
  subst. apply q_le_distinct_base.
Qed.

Definition r_distinct_add : qrule :=
  mk_qrule "DISTINCT-add" Down f_distinct_add f_distinct_add_sound.

(** UNION -> UNION ALL (rule 2) *)
Definition f_union_all (q : query) : list query :=
  match q with QUnion a b => [QUnionAll a b] | _ => [] end.

Theorem f_union_all_sound : forall q q', In q' (f_union_all q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_union_base.
Qed.

Definition r_union_all : qrule := mk_qrule "UNION->UNION-ALL" Up f_union_all f_union_all_sound.

(** UNION ALL -> UNION (rule 2 backwards) *)
Definition f_union_distinct (q : query) : list query :=
  match q with QUnionAll a b => [QUnion a b] | _ => [] end.

Theorem f_union_distinct_sound : forall q q', In q' (f_union_distinct q) -> dle q_le Down q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_union_base.
Qed.

Definition r_union_distinct : qrule :=
  mk_qrule "UNION-ALL->UNION" Down f_union_distinct f_union_distinct_sound.

(** A EXCEPT B -> A (rule 3) *)
Definition f_except_left (q : query) : list query :=
  match q with QExcept a _ => [a] | _ => [] end.

Theorem f_except_left_sound : forall q q', In q' (f_except_left q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_except_base.
Qed.

Definition r_except_left : qrule := mk_qrule "EXCEPT->left" Up f_except_left f_except_left_sound.

(** A INTERSECT B -> A UNION B (rule 4) *)
Definition f_intersect_union (q : query) : list query :=
  match q with QIntersect a b => [QUnion a b] | _ => [] end.

Theorem f_intersect_union_sound :
  forall q q', In q' (f_intersect_union q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_inter_base.
Qed.

Definition r_intersect_union : qrule :=
  mk_qrule "INTERSECT->UNION" Up f_intersect_union f_intersect_union_sound.

(** A UNION B -> A INTERSECT B (rule 4 backwards) *)
Definition f_union_intersect (q : query) : list query :=
  match q with QUnion a b => [QIntersect a b] | _ => [] end.

Theorem f_union_intersect_sound :
  forall q q', In q' (f_union_intersect q) -> dle q_le Down q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_inter_base.
Qed.

Definition r_union_intersect : qrule :=
  mk_qrule "UNION->INTERSECT" Down f_union_intersect f_union_intersect_sound.

(** INNER JOIN -> LEFT JOIN (rule 17) *)
Definition f_inner_left (q : query) : list query :=
  match q with QInnerJoin p a b => [QLeftJoin (arity b) p a b] | _ => [] end.

Theorem f_inner_left_sound : forall q q', In q' (f_inner_left q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_inner_left.
Qed.

Definition r_inner_left : qrule := mk_qrule "INNER->LEFT-JOIN" Up f_inner_left f_inner_left_sound.

(** LEFT JOIN -> INNER JOIN (rule 17 backwards) *)
Definition f_left_inner (q : query) : list query :=
  match q with QLeftJoin _ p a b => [QInnerJoin p a b] | _ => [] end.

Theorem f_left_inner_sound : forall q q', In q' (f_left_inner q) -> dle q_le Down q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_inner_left.
Qed.

Definition r_left_inner : qrule := mk_qrule "LEFT->INNER-JOIN" Down f_left_inner f_left_inner_sound.
