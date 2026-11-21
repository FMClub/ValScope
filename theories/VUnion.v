(** VUnion.v: value queries combined with UNION ALL.

    [q1 UNION ALL q2] returns the rows of [q1] followed by the rows of [q2].  A value
    mutation of one arm changes the rows of that arm only, so the rows of the whole union
    still correspond one to one: the mutated arm's rows by [vmut_sound], the other arm's
    rows to themselves (every value relation is reflexive).  The arms must have the same
    number of columns, which the mutator checks.

    The same holds for a mutation of the HAVING predicate of one arm: the result of the
    union is a sub-list (or super-list) of the original. *)

From Coq Require Import List String Reals Lra Lia.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Rule Engine Value VEngine VHaving.

Inductive vtop : Type :=
  | VOne      : vquery -> vtop
  | VUnionAll : vtop -> vtop -> vtop.

Fixpoint teval (env : venv) (db : db_t) (t : vtop) : list (list (option R)) :=
  match t with
  | VOne v => veval env db v
  | VUnionAll a b => teval env db a ++ teval env db b
  end.

(** The number of columns, when all arms agree on it. *)
Fixpoint tarity (t : vtop) : option nat :=
  match t with
  | VOne v => Some (List.length (vitems v))
  | VUnionAll a b =>
      match tarity a, tarity b with
      | Some n, Some m => if Nat.eqb n m then Some n else None
      | _, _ => None
      end
  end.

(** ---------------- facts ---------------- *)

Lemma rel_holds_refl : forall r x, rel_holds r x x.
Proof. intros [] [x|]; simpl; try exact I; try lra; split; intro; lra. Qed.

Lemma row_rel_refl : forall r j x, j < List.length x -> row_rel r j x x.
Proof.
  intros r j x H. destruct (nth_split x None H) as [pre [post [Ex Hl]]].
  exists pre, (nth j x None), (nth j x None), post.
  repeat split; try exact Ex; try exact Hl. apply rel_holds_refl.
Qed.

Lemma veval_length : forall env db v row, In row (veval env db v) -> List.length row = List.length (vitems v).
Proof.
  intros env db v row H. unfold veval in H. apply in_map_iff in H as [g [<- _]]. apply map_length.
Qed.

Lemma teval_length : forall env db t n row, tarity t = Some n -> In row (teval env db t) -> List.length row = n.
Proof.
  induction t as [v|a IHa b IHb]; intros n row Ht Hin; simpl in *.
  - inversion Ht; subst. eapply veval_length; exact Hin.
  - destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; try discriminate.
    destruct (Nat.eqb na nb) eqn:E; try discriminate. apply Nat.eqb_eq in E. inversion Ht; subst.
    apply in_app_or in Hin as [H|H]; [apply (IHa n row eq_refl H) | apply (IHb n row eq_refl H)].
Qed.

Lemma forall2_refl_rows : forall r j (l : list (list (option R))),
  (forall row, In row l -> j < List.length row) -> Forall2 (row_rel r j) l l.
Proof.
  intros r j l H. induction l as [|x l IH]; constructor.
  - apply row_rel_refl. apply H. left. reflexivity.
  - apply IH. intros row Hr. apply H. right. exact Hr.
Qed.

Lemma sub_refl : forall {X : Type} (l : list X), Sub l l.
Proof. intros X l. induction l; constructor; assumption. Qed.

Lemma sub_app : forall {X : Type} (a a' b b' : list X), Sub a a' -> Sub b b' -> Sub (a ++ b) (a' ++ b').
Proof. intros X a a' b b' H1 H2. induction H1; simpl; try constructor; assumption. Qed.

(** ---------------- the value mutator on unions ---------------- *)

Section TEngine.
Variable rs : list vrule.

Lemma vmut_shape : forall v name r j v',
  In (name, (r, (j, v'))) (vmut rs v) ->
  j < List.length (vitems v) /\ List.length (vitems v') = List.length (vitems v).
Proof.
  intros v name r j v' H. unfold vmut in H.
  apply in_flat_map in H as [[[pre a] post] [Hs Hm]]. simpl in Hm.
  apply in_map_iff in Hm as [[n [r0 a']] [E _]]. simpl in E. inversion E; subst. clear E.
  apply splits_spec in Hs. rewrite vitems_with_items, Hs, !app_length. simpl. lia.
Qed.

Definition tmutant : Type := (string * (vrel * (nat * vtop)))%type.

Definition tmap (f : vtop -> vtop) (l : list tmutant) : list tmutant :=
  map (fun m => (fst m, (fst (snd m), (fst (snd (snd m)), f (snd (snd (snd m))))))) l.

Fixpoint tmut (t : vtop) : list tmutant :=
  match t with
  | VOne v => map (fun m => (fst m, (fst (snd m), (fst (snd (snd m)), VOne (snd (snd (snd m)))))))
                  (vmut rs v)
  | VUnionAll a b =>
      match tarity t with
      | Some _ => tmap (fun a' => VUnionAll a' b) (tmut a) ++ tmap (fun b' => VUnionAll a b') (tmut b)
      | None => []
      end
  end.

(** Mutants keep the number of columns, and the mutated column exists. *)
Lemma tmut_shape : forall t name r j t',
  In (name, (r, (j, t'))) (tmut t) ->
  exists n, tarity t = Some n /\ tarity t' = Some n /\ j < n.
Proof.
  induction t as [v|a IHa b IHb]; intros name r j t' H; simpl in H.
  - apply in_map_iff in H as [[n0 [r0 [j0 v']]] [E Hin]]. simpl in E. inversion E; subst.
    destruct (vmut_shape _ _ _ _ _ Hin) as [Hj Hl].
    exists (List.length (vitems v)). simpl. rewrite Hl. auto.
  - destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; simpl in H;
      rewrite ?Ea, ?Eb in H; try contradiction.
    destruct (Nat.eqb na nb) eqn:E; [|contradiction]. apply Nat.eqb_eq in E. subst nb.
    apply in_app_or in H as [H|H]; unfold tmap in H; apply in_map_iff in H as [[n0 [r0 [j0 x]]] [Em Hin]];
      simpl in Em; inversion Em; subst.
    + destruct (IHa _ _ _ _ Hin) as [n [Ha [Ha' Hj]]].
      assert (n = na) by congruence. subst n.
      exists na. simpl. rewrite Ea, Eb, Ha', Nat.eqb_refl. auto.
    + destruct (IHb _ _ _ _ Hin) as [n [Hb [Hb' Hj]]].
      assert (n = na) by congruence. subst n.
      exists na. simpl. rewrite Ea, Eb, Hb', Nat.eqb_refl. auto.
Qed.

Theorem tmut_sound : forall t name r j t',
  In (name, (r, (j, t'))) (tmut t) ->
  forall env db, Forall2 (row_rel r j) (teval env db t) (teval env db t').
Proof.
  induction t as [v|a IHa b IHb]; intros name r j t' H env db; simpl in H.
  - apply in_map_iff in H as [[n0 [r0 [j0 v']]] [E Hin]]. simpl in E. inversion E; subst.
    simpl. exact (vmut_sound rs _ _ _ _ _ Hin env db).
  - destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; simpl in H;
      rewrite ?Ea, ?Eb in H; try contradiction.
    destruct (Nat.eqb na nb) eqn:E; [|contradiction]. apply Nat.eqb_eq in E. subst nb.
    apply in_app_or in H as [H|H]; unfold tmap in H; apply in_map_iff in H as [[n0 [r0 [j0 x]]] [Em Hin]];
      simpl in Em; inversion Em; subst; simpl.
    + apply Forall2_app; [exact (IHa _ _ _ _ Hin env db)|].
      destruct (tmut_shape a _ _ _ _ Hin) as [n [Ha [_ Hj]]].
      assert (n = na) by congruence. subst n.
      apply forall2_refl_rows. intros row Hr. rewrite (teval_length env db b na row Eb Hr). exact Hj.
    + apply Forall2_app; [|exact (IHb _ _ _ _ Hin env db)].
      destruct (tmut_shape b _ _ _ _ Hin) as [n [Hb [_ Hj]]].
      assert (n = na) by congruence. subst n.
      apply forall2_refl_rows. intros row Hr. rewrite (teval_length env db a na row Ea Hr). exact Hj.
Qed.


(** A value mutant changes select items only: every arm keeps its grouping keys, its
    HAVING predicate and its source.  So anything computed from those alone (the groups
    that survive HAVING, and a window function over them) is the same for the original
    and the mutant, which is why such a window can be an opaque item ([AOpaque]). *)
Fixpoint same_frame (t t' : vtop) : Prop :=
  match t, t' with
  | VOne v, VOne v' => exists i, v' = with_items v i
  | VUnionAll a b, VUnionAll a' b' => same_frame a a' /\ same_frame b b'
  | _, _ => False
  end.

Lemma same_frame_refl : forall t, same_frame t t.
Proof.
  induction t as [v|a IHa b IHb]; simpl.
  - exists (vitems v). destruct v; reflexivity.
  - split; assumption.
Qed.

Lemma vmut_frame : forall v name r j v', In (name, (r, (j, v'))) (vmut rs v) -> exists i, v' = with_items v i.
Proof.
  intros v name r j v' H. unfold vmut in H.
  apply in_flat_map in H as [[[pre a] post] [_ Hm]]. simpl in Hm.
  apply in_map_iff in Hm as [[n [r0 a']] [E _]]. simpl in E. inversion E; subst.
  eexists. reflexivity.
Qed.

Theorem tmut_frame : forall t name r j t', In (name, (r, (j, t'))) (tmut t) -> same_frame t t'.
Proof.
  induction t as [v|a IHa b IHb]; intros name r j t' H; simpl in H.
  - apply in_map_iff in H as [[n0 [r0 [j0 v']]] [E Hin]]. simpl in E. inversion E; subst.
    exact (vmut_frame _ _ _ _ _ Hin).
  - destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; simpl in H;
      rewrite ?Ea, ?Eb in H; try contradiction.
    destruct (Nat.eqb na nb); [|contradiction].
    apply in_app_or in H as [H|H]; unfold tmap in H; apply in_map_iff in H as [[n0 [r0 [j0 x]]] [Em Hin]];
      simpl in Em; inversion Em; subst; simpl; split.
    + exact (IHa _ _ _ _ Hin).
    + apply same_frame_refl.
    + apply same_frame_refl.
    + exact (IHb _ _ _ _ Hin).
Qed.

End TEngine.

(** ---------------- HAVING mutation of an arm ---------------- *)

Definition t_sub (t t' : vtop) : Prop := forall env db, Sub (teval env db t) (teval env db t').

Section THaving.
Variable prs : list prule.
Variable qrs : list qrule.

Fixpoint thmut (d : dir) (t : vtop) : list (string * vtop) :=
  match t with
  | VOne v => map (fun m => (fst m, VOne (snd m))) (hmut prs qrs d v)
  | VUnionAll a b =>
      map (fun m => (fst m, VUnionAll (snd m) b)) (thmut d a) ++
      map (fun m => (fst m, VUnionAll a (snd m))) (thmut d b)
  end.

Theorem thmut_sound : forall d t name t', In (name, t') (thmut d t) -> dle t_sub d t t'.
Proof.
  intros d t. induction t as [v|a IHa b IHb]; intros name t' H; simpl in H.
  - apply in_map_iff in H as [[n v'] [E Hin]]. simpl in E. inversion E; subst.
    pose proof (hmut_sound prs qrs d _ _ _ Hin) as K.
    destruct d; simpl in *; intros env db; apply K.
  - apply in_app_or in H as [H|H]; apply in_map_iff in H as [[n x] [E Hin]]; simpl in E; inversion E; subst.
    + pose proof (IHa _ _ Hin) as K. destruct d; simpl in *; intros env db; simpl;
        apply sub_app; try apply K; apply sub_refl.
    + pose proof (IHb _ _ Hin) as K. destruct d; simpl in *; intros env db; simpl;
        apply sub_app; try apply K; apply sub_refl.
Qed.

End THaving.
