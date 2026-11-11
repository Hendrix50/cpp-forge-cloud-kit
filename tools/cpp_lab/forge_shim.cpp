// Linked into every player program by the lab (and later by the phone compiler service).
// Makes output unbuffered so everything a program printed before a crash or a trap is still shown.
#include <cstdio>
namespace {
struct ForgeShim { ForgeShim() { std::setvbuf(stdout, nullptr, _IONBF, 0); std::setvbuf(stderr, nullptr, _IONBF, 0); } };
ForgeShim forge_shim_instance;
}
