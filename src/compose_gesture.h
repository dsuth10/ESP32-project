#pragma once
#include <stdint.h>

// Pure transition function: keeps serial feedback and drawing alive during a
// long press. Short release latches; next touch stops; long release stops.
namespace ComposeGesture {
enum Action { None, Start, Stop, Library, Paste };
struct State {
  int active; bool latched, down, swallowed; uint32_t started;
  constexpr State(int a=-1,bool l=false,bool d=false,bool s=false,uint32_t t=0)
      : active(a),latched(l),down(d),swallowed(s),started(t) {}
};
struct Step {
  State next; Action action; int button;
  constexpr Step(State s,Action a=None,int b=-1):next(s),action(a),button(b) {}
};
constexpr Step update(State s,bool down,int target,uint32_t now,bool connected) {
  return s.active>=0 && (!connected || uint32_t(now-s.started)>=60000 || (s.latched && down && !s.down))
    ? Step(State(-1,false,down,down),Stop,s.active)
    : s.active>=0 && !s.latched && !down && s.down
    ? (uint32_t(now-s.started)>=350 ? Step(State(),Stop,s.active) : Step(State(s.active,true,false,false,s.started)))
    : !down ? Step(State(s.active,s.latched,false,false,s.started))
    : (s.down || s.swallowed) ? Step(State(s.active,s.latched,true,s.swallowed,s.started))
    : connected && target>=0 && target<=2 ? Step(State(target,false,true,false,now),Start,target)
    : connected && (target==3 || target==4) ? Step(State(-1,false,true,true),target==3?Library:Paste,target)
    : Step(State(-1,false,true,false));
}
// Compile-time regression checks run in the actual target compiler on every build.
constexpr Step begin=update(State(),true,0,100,true);
constexpr Step tapped=update(begin.next,false,-1,200,true);
constexpr Step stopped=update(tapped.next,true,3,300,true);
static_assert(begin.action==Start && begin.button==0,"Compose starts on touch edge");
static_assert(tapped.next.latched && tapped.action==None,"Short tap remains recording");
static_assert(stopped.action==Stop && stopped.next.active==-1,"Next touch stops without library action");
static_assert(update(begin.next,false,-1,500,true).action==Stop,"Hold releases recording");
static_assert(update(begin.next,true,0,60100,true).action==Stop,"60-second cap releases keys");
static_assert(update(begin.next,true,0,200,false).action==Stop,"Connection loss releases keys");
static_assert(update(State(),true,4,100,true).action==Paste,"Paste has a distinct one-shot action");
static_assert(update(update(State(),true,4,100,true).next,true,4,200,true).action==None,"Held paste never repeats");
static_assert(update(State(),true,2,100,true).button==2,"Images uses its own recording gesture");
static_assert(update(State(),true,3,100,true).action==Library,"Library is a single tap");
static_assert(update(State(),true,0,100,false).action==None,"No keyboard dispatch without BLE");
}
