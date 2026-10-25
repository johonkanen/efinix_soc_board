import pcbnew, sys
b=pcbnew.LoadBoard(sys.argv[1])
refs={f"C{i}" for i in list(range(509,566))+list(range(803,836))}
n=0
for fp in b.GetFootprints():
    if fp.GetReference() in refs and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT); n+=1
pcbnew.SaveBoard(sys.argv[1], b); print("flipped", n)
