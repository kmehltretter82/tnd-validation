import TNDLib

namespace TNDTask

theorem cantorFlipInvolution (b : Bool) : TNDLib.Cantor.flip (TNDLib.Cantor.flip b) = b :=
  Bool.rec (motive := fun x => TNDLib.Cantor.flip (TNDLib.Cantor.flip x) = x) rfl rfl b

end TNDTask
