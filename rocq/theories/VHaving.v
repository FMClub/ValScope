(** VHaving.v: mutation of the HAVING predicate (rules 15 and 16 of mutation.md).

    A HAVING predicate is mutated by the same predicate rules and the same engine
    as WHERE and ON ([Engine.mut_p]): "HAVING cond -> TRUE" is the rule [cond->TRUE]
    at the HAVING position, and comparison weakening, dropping a conjunct, IN and
    EXISTS subqueries inside HAVING all come with it.  No new rule is needed.

    The effect is on the set of groups: with [Up] the mutant outputs the same rows
    plus possibly more, with [Down] a subset. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule Engine Value.

Section Having.
Variable prs : list prule.
Variable qrs : list qrule.

Definition hmut (d : dir) (v : vquery) : list (string * vquery) :=
  match v with
  | VProj _ _ => []
  | VGroup _ _ h _ | VGlobal _ h _ => lmap (with_having v) (mut_p prs qrs d h)
  end.

Theorem hmut_sound : forall d v name v',
  In (name, v') (hmut d v) -> dle v_sub d v v'.
Proof.
  intros d v name v' H.
  assert (K : exists h h', vhaving v = h /\ v' = with_having v h' /\
                           vhaving (with_having v h') = h' /\ dle p_le d h h').
  { destruct v as [i q|k i h q|i h q]; simpl in H; try contradiction;
      unfold lmap in H; apply in_map_iff in H as [[n h'] [E Hin]];
      simpl in E; inversion E; subst; exists h, h';
      (repeat split; try reflexivity); exact (mut_p_sound prs qrs d h _ h' Hin). }
  destruct K as [h [h' [E [-> [E' Hd]]]]].
  destruct d; simpl in *.
  - apply (having_mono v h h' E E' Hd).
  - apply (having_anti v h h' E E' Hd).
Qed.

End Having.
