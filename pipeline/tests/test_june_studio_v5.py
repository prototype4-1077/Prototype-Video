"""Regression for the curve-bounds false alarm found in the v5 pose audit."""
import unittest
from types import SimpleNamespace as NS

import numpy as np

from pipeline.blender.audit_june_wardrobe import projected_mesh_bounds


class WardrobeFramingTests(unittest.TestCase):
    def test_projects_evaluated_vertices_instead_of_oversized_curve_bounds(self):
        class Vertices:
            def __len__(self):return 2
            def foreach_get(self, name, target):
                if name!='co':raise AssertionError(name)
                target[:]=(-.5,-.3,0.,.5,.8,0.)

        projection=np.eye(4)
        transform=np.eye(4);transform[0,3]=.25
        evaluated=NS(matrix_world=transform,bound_box=[(-100,-100,-100),(100,100,100)],
                     to_mesh=lambda:NS(vertices=Vertices()),to_mesh_clear=lambda:None)
        obj=NS(evaluated_get=lambda _:evaluated)
        camera=NS(matrix_world=NS(inverted=lambda:np.eye(4)),
                  calc_matrix_camera=lambda *a,**kw:projection)
        scene=NS(camera=camera,render=NS(resolution_x=1280,resolution_y=720,pixel_aspect_x=1.,pixel_aspect_y=1.))
        bpy=NS(context=NS(evaluated_depsgraph_get=lambda:None))
        np.testing.assert_allclose(projected_mesh_bounds(bpy,scene,[obj]),(.375,.875,.35,.9),atol=1e-7)
        projection[3,3]=-1.
        with self.assertRaisesRegex(ValueError,'behind-camera'):
            projected_mesh_bounds(bpy,scene,[obj])


if __name__=='__main__':unittest.main()
