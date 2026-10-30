import Init

/-! List products with algebraic laws supplied explicitly. -/

namespace TNDLib.Algebra

/-- Fold a binary operation over a list, starting from the supplied identity. -/
def product (op : α → α → α) (one : α) : List α → α
  | [] => one
  | x :: xs => op x (product op one xs)

/-- Products preserve append whenever the supplied operation is associative and unital. -/
theorem productAppend (op : α → α → α) (one : α)
    (assoc : ∀ a b c, op (op a b) c = op a (op b c))
    (leftIdentity : ∀ a, op one a = a) :
    (xs ys : List α) → product op one (xs ++ ys) = op (product op one xs) (product op one ys)
  | [], ys => (leftIdentity (product op one ys)).symm
  | x :: xs, ys =>
    (congrArg (op x) (productAppend op one assoc leftIdentity xs ys)).trans
      (assoc x (product op one xs) (product op one ys)).symm

/-- The empty product is the supplied identity element. -/
theorem productNil (op : α → α → α) (one : α) : product op one [] = one := rfl

/-- A nonempty product exposes its leading operation. -/
theorem productCons (op : α → α → α) (one x : α) (xs : List α) :
    product op one (x :: xs) = op x (product op one xs) := rfl

/-- Singleton products agree with their element when the identity is right unital. -/
theorem productSingleton (op : α → α → α) (one x : α)
    (rightIdentity : ∀ a, op a one = a) : product op one [x] = x :=
  rightIdentity x

end TNDLib.Algebra
