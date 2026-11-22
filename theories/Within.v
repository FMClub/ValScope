(** Within.v: a rule that is sound in a class of worlds only, plugged into the engine.

    The rules of StdRules.v and ExtraRules.v hold in every world.  A rule which
    relies on a property of one dialect does not; it is proved for the class [W] of
    the worlds which have that property, packaged as a [prule_in W] or a
    [qrule_in W], and given to [mutate_within W].

    The example: swapping the operands of [+] in a comparison.  The abstract model
    does not ask [vadd] to be commutative, so this is no rule of every world; it is
    one in the worlds where [vadd] commutes up to the collation.  The rewritten
    condition has the same truth value, so the rule is given in both directions. *)

From Coq Require Import List String ZArith.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule Engine Registry Counter.

Definition add_commutes (db : db_t) : Prop :=
  forall x y, veq db (vadd db x y) (vadd db y x) = true.

(** The class is not empty: the worlds of Counter.v are in it.  A rule of an empty
    class would be sound for no reason, so a class comes with such a witness; that
    the tested DBMS behaves as a world of the class is the claim that is trusted. *)
Lemma add_commutes_inhabited : forall t, add_commutes (ex_world t).
Proof.
  intros t x y. simpl. destruct x, y; simpl; try reflexivity.
  rewrite Z.add_comm. unfold veqb. destruct (value_eq_dec _ _); congruence.
Qed.

Definition f_add_swap (p : pred) : list pred :=
  match p with
  | PCmp c (EAdd a b) e => [PCmp c (EAdd b a) e]
  | _ => []
  end.

Lemma add_swap_eq : forall db ctx c a b e, add_commutes db ->
  eval_p db ctx (PCmp c (EAdd a b) e) = eval_p db ctx (PCmp c (EAdd b a) e).
Proof. intros db ctx c a b e H. simpl. apply vcmp_compat; [apply H|apply veq_refl]. Qed.

Lemma f_add_swap_sound : forall d p p', In p' (f_add_swap p) ->
  dle (p_le_within add_commutes) d p p'.
Proof.
  intros d p p' H. destruct p as [| |c x e| | | | | | | | | |]; try contradiction.
  destruct x; try contradiction. destruct H as [<-|[]].
  destruct d; simpl; intros db HW ctx;
    [rewrite (add_swap_eq db ctx c x1 x2 e HW)|rewrite <- (add_swap_eq db ctx c x1 x2 e HW)];
    apply tv_le_refl.
Qed.

Definition r_add_swap (d : dir) : prule_in add_commutes :=
  mk_prule_in add_commutes "add-swap-operands" d f_add_swap (f_add_swap_sound d).

(** The mutator of the worlds where [+] commutes: every rule of the registry, and
    this one. *)
Definition mutate_add_commutes : dir -> query -> list (string * query) :=
  mutate_within add_commutes [r_add_swap Up; r_add_swap Down] [].

Theorem mutate_add_commutes_sound : forall d q name q',
  In (name, q') (mutate_add_commutes d q) -> dle (q_le_within add_commutes) d q q'.
Proof. intros d q name q'. apply mutate_within_sound. Qed.

Print Assumptions mutate_add_commutes_sound.

(** The rule fires under a WHERE, next to the rules of the registry. *)
Example add_swap_fires :
  In ("add-swap-operands"%string,
      QWhere (PCmp CLt (EAdd (ECol 1) (ECol 0)) (EConst VNull)) (QTable 0 2))
     (mutate_add_commutes Up
        (QWhere (PCmp CLt (EAdd (ECol 0) (ECol 1)) (EConst VNull)) (QTable 0 2))).
Proof. vm_compute. tauto. Qed.
