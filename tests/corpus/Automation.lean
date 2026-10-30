/- Development-only automation probes; this file is not imported by TNDLib. -/
import Init

namespace TNDTests.Automation

theorem additiveBound (n m : Nat) : n ≤ n + m := by
  omega
  done

#print axioms additiveBound

theorem reverseSingleton (x : Nat) : List.reverse [x] = [x] := by
  simp
  done

#print axioms reverseSingleton

theorem closedArithmetic : (3 : Nat) + 4 = 7 := by
  decide
  done

#print axioms closedArithmetic

/- This is a deliberately nonconstructive control, never a library import. -/
theorem classicalControl (P : Prop) : P ∨ ¬P := by
  exact Classical.em P
  done

#print axioms classicalControl

end TNDTests.Automation
