MASAFI-SimTwin
==============

MASAFI-SimTwin is the graphical frontend of the MASAFI family of simulation
libraries (Manufacturing, Automation & Simulation Analytics for Factory
Integration).  It holds no simulation engine of its own: it is the model editor,
the animation and the statistics laid over the libraries that do the
simulating.

The family it is built for:

======================  ===============================================  ===========
Library                 What it is                                       Status
======================  ===============================================  ===========
MASAFI-sim-petri        Petri nets: modelling, analysis and simulation   In progress
MASAFI-sim-blocks       Block-based discrete event simulation            Planned
MASAFI-sim-blocks-2d    The blocks laid out and animated in 2D           Planned
MASAFI-sim-blocks-3d    The blocks laid out and animated in 3D           Planned
======================  ===============================================  ===========

What works today is the place/transition Petri net editor: a net can be drawn,
named, described, saved, recovered, undone, copied and exported to PDF.  Nothing
runs a net yet.

MASAFI-SimTwin is free software, released under the GNU General Public License,
version 3 or later.

.. toctree::
   :maxdepth: 2
   :caption: Using MASAFI-SimTwin

   using/manual/index
   using/install/index

.. toctree::
   :maxdepth: 2
   :caption: Developing MASAFI-SimTwin

   developing/setup
   developing/stack
   developing/petri_nets
   developing/process_flow
   developing/animation_2d
   developing/animation_3d
   developing/digital_shadow
   developing/digital_twin
   developing/api
