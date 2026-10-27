/*
 *
 * This file is part of Optolithium lithography modelling software.
 *
 * Copyright (C) 2015 Alexei Gladkikh
 *
 * This software is dual-licensed: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version only for NON-COMMERCIAL usage.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 *
 * If you are interested in other licensing models, including a commercial-
 * license, please contact the author at gladkikhalexei@gmail.com
 *
 */

/* Release the GIL around native calls so Qt's GUI thread can continue handling
 * events while the numerical core runs from a QThread. */
%module(threads="1") optolithiumc
%{
    #define SWIG_FILE_WITH_INIT

    /* Includes the header in the wrapper code */
    #include "opl_contours.h"
    #include "opl_geometry.h"
    #include "opl_iter.h"
    #include "opl_capi.h"
    #include "opl_sim.h"

    static PyObject* ctypes_module;
    static PyObject* ctypes_module_cast;
    static PyObject* ctypes_module_c_void_p;

#if PY_MAJOR_VERSION >= 3
#define PyInt_AsUnsignedLongLongMask PyLong_AsUnsignedLongLongMask
#define PyString_AsString(op) PyUnicode_AsUTF8(op)
#endif

#ifdef __cplusplus
static inline PyObject* SWIG_Python_AppendOutput(PyObject* result, PyObject* obj) {
    return SWIG_Python_AppendOutput(result, obj, 0);
}
#endif

    int load_ctypes_module(void) {
        ctypes_module = PyImport_ImportModule("ctypes");
        if (!ctypes_module) {
            PyErr_SetString(PyExc_RuntimeError, "Can't load ctypes module!");
            return -1;
        }

        ctypes_module_cast = PyObject_GetAttrString(ctypes_module, "cast");
        if (!ctypes_module_cast) {
            PyErr_SetString(PyExc_RuntimeError, "ctypes.cast function not found in ctypes module!");
            return -1;
        }

        ctypes_module_c_void_p = PyObject_GetAttrString(ctypes_module, "c_void_p");
        if (!ctypes_module_c_void_p) {
            PyErr_SetString(PyExc_RuntimeError, "ctypes.c_void_p class not found in ctypes module!");
            return -1;
        }
        return 0;
    }

%}

%init {
    load_ctypes_module();
}

/* ---------------------------------------------------------------------------- */

%define %ctypes_callback(typename)
    %typemap(in) typename {
        PyObject* args = Py_BuildValue("(OO)", $input, ctypes_module_c_void_p);
        if (!args) {
            SWIG_exception_fail(SWIG_ERROR, "Py_BuildValue: can't create input args tuple!");
        }
        PyObject* pointer = PyObject_CallObject(ctypes_module_cast, args);
        if (!pointer) {
            SWIG_exception_fail(SWIG_ERROR, "PyObject_CallObject: convert function to c_void_p failed!");
        }
        PyObject* address = PyObject_GetAttrString(pointer, "value");
        if (!address) {
            SWIG_exception_fail(SWIG_ERROR, "PyObject_GetAttrString: get address from c_void_p failed!");
        }
        uint64_t address_value = PyInt_AsUnsignedLongLongMask(address);
        //printf("Address is %016llX\n", address_value);
        //PyObject_Print(address,stdout,Py_PRINT_RAW);
        if (address_value == (uint64_t)-1) {
            if (PyErr_Occurred()) {
                PyObject *errtype, *errvalue, *traceback;
                PyErr_Fetch(&errtype, &errvalue, &traceback);
                if (errvalue != nullptr) {
                    PyObject *str = PyObject_Str(errvalue);
                    std::string header_string("PyLong_AsUnsignedLongLong: ");
                    const char *cstr = PyString_AsString(str);
                    std::string message_string(cstr ? cstr : "");
                    SWIG_exception_fail(SWIG_ERROR, (header_string + message_string).c_str());
                    Py_DECREF(str);
                }
                Py_XDECREF(errvalue);
                Py_XDECREF(errtype);
                Py_XDECREF(traceback);
            }
        }
        $1 = reinterpret_cast<typename>(address_value);
    }
%enddef

/* ---------------------------------------------------------------------------- */

%include <typemaps.i>
%include <stdint.i>
%include <complex.i>
%include <std_shared_ptr.i>
%include <std_vector.i>
%include <std_string.i>
%include <armanpy.i>

/* ---------------------------------------------------------------------------- */

%ctypes_callback(source_shape_expr_t)
%ctypes_callback(rate_model_expr_t)
%ctypes_callback(pupil_filter_expr_t)

/* ---------------------------------------------------------------------------- */

%shared_ptr(geometry::Point2d)
%shared_ptr(geometry::Edge2d)

%shared_ptr(geometry::Point3d)
%shared_ptr(geometry::Edge3d)

%shared_ptr(geometry::Triangle3d)
%shared_ptr(geometry::Surface3d)

%shared_ptr(geometry::AbstractGeometry)
%shared_ptr(geometry::PolygonGeometry)
%shared_ptr(geometry::RectangleGeometry)

%shared_ptr(oplc::AbstractMaskGeometry)
%shared_ptr(oplc::Region)
%shared_ptr(oplc::Box)

%shared_ptr(oplc::AbstractResistRateModel)
%shared_ptr(oplc::ResistRateModelExpression)
%shared_ptr(oplc::ResistRateModelSheet)
%shared_ptr(oplc::ResistRateModelDepthSheet)

%shared_ptr(oplc::AbstractSourceShapeModel)
%shared_ptr(oplc::SourceShapeModelPlugin)
%shared_ptr(oplc::SourceShapeModelSheet)

%shared_ptr(oplc::AbstractPupilFilterModel)
%shared_ptr(oplc::PupilFilterModelPlugin)
%shared_ptr(oplc::PupilFilterModelSheet)
%shared_ptr(oplc::PupilFilterModelEmpty)

%shared_ptr(oplc::ExposureResistModel)
%shared_ptr(oplc::PebResistModel)

%shared_ptr(oplc::AbstractWaferLayer)
%shared_ptr(oplc::StandardWaferLayer)
%shared_ptr(oplc::ResistWaferLayer)
%shared_ptr(oplc::ConstantWaferLayer)
%shared_ptr(oplc::WaferStack)

%shared_ptr(oplc::Mask)
%shared_ptr(oplc::ImagingTool)
%shared_ptr(oplc::Diffraction)
%shared_ptr(oplc::SourceShape)
%shared_ptr(oplc::Exposure)
%shared_ptr(oplc::PostExposureBake)
%shared_ptr(oplc::Development)
%shared_ptr(oplc::OpticalTransferFunction)

%shared_ptr(oplc::AbstractResistSimulations)
%shared_ptr(oplc::ResistVolume)
%shared_ptr(oplc::ResistProfile)

/* ---------------------------------------------------------------------------- */

%template(Triangle3dArray) std::vector<std::shared_ptr<geometry::Triangle3d> >;
%template(PolygonsArray) std::vector<std::shared_ptr<geometry::PolygonGeometry> >;
%template(Points2dArray) std::vector<std::shared_ptr<geometry::Point2d> >;
%template(Points3dArray) std::vector<std::shared_ptr<geometry::Point3d> >;
%template(RegionsArray) std::vector<std::shared_ptr<oplc::Region> >;
%template(DoubleArray) std::vector<double>;

/* ---------------------------------------------------------------------------- */

%exception {
    try {
        $action
    } catch (const std::length_error& error) {
        PyErr_SetString(PyExc_IndexError, error.what());
        SWIG_fail;
    } catch (const std::out_of_range& error) {
        PyErr_SetString(PyExc_IndexError, error.what());
        SWIG_fail;
    } catch (const std::invalid_argument& error) {
        PyErr_SetString(PyExc_ValueError, error.what());
        SWIG_fail;
    } catch (const std::range_error& error) {
        PyErr_SetString(PyExc_IndexError, error.what());
        SWIG_fail;
    } catch (const std::runtime_error& error) {
        PyErr_SetString(PyExc_RuntimeError, error.what());
        SWIG_fail;
    } catch (const std::exception& error) {
        PyErr_SetString(PyExc_Exception, error.what());
        SWIG_fail;    
    }
}

/* ---------------------------------------------------------------------------- */

namespace geometry {

    %extend Point2d {
        %rename(__getitem__) operator[];
        %rename(__len__) length;
        %rename(__repr__) str;

        %pythoncode %{
            def round(self, ndigits):
                return self.__class__(round(self.x, ndigits), round(self.y, ndigits))

            def __hash__(self):
                return hash((self.x, self.y))
        %}
    }

    %ignore operator *;
    %ignore operator /;

    %extend Edge2d {
        %rename(__str__) str;
    }

    %extend Point3d {
        %rename(__getitem__) operator[];
        %rename(__len__) length;
        %rename(__repr__) str;
    }

    %extend Edge3d {
        %rename(__str__) str;
    }

    %extend Triangle3d {
        %rename(__getitem__) operator[];
        %rename(__len__) length;
        %rename(__repr__) str;

        %rename(_get_a) a;
        %rename(_get_b) b;
        %rename(_get_c) c;

        %pythoncode %{
            a = property(_get_a)
            b = property(_get_b)
            c = property(_get_c)
        %}
    }

    %extend Surface3d {
        %rename(_get_points) points;
        %rename(_get_triangles) triangles;

        %rename(_get_x) x;
        %rename(_get_y) y;
        %rename(_get_z) z;

        %pythoncode %{
            points = property(_get_points)
            triangles = property(_get_triangles)

            x = property(_get_x)
            y = property(_get_y)
            z = property(_get_z)
        %}
    }

    // ArrayOfSharedPoints2d
    %extend std::vector<std::shared_ptr<Point2d> > {
        std::string __str__() {
            std::ostringstream result;
            for (auto item : *$self) {
                result << " " << item->str() << ", " << std::endl;
            }
            return result.str();
        }
    }

    // ArrayOfSharedPoints3d
    %extend std::vector<std::shared_ptr<Point3d> > {
        std::string __str__() {
            std::ostringstream result;
            for (auto item : *$self) {
                result << " " << item->str() << ", " << std::endl;
            }
            return result.str();
        }
    }

    %extend AbstractGeometry {
        %rename(__getitem__) at;
        %rename(__len__) length;
        %rename(__str__) str;

        %pythoncode %{
            def __iter__(self):
                for k in range(len(self)):
                    yield self[k]
        %}
    }


    // ArrayOfSharedPolygons
    %extend std::vector<std::shared_ptr<PolygonGeometry> > {
        std::string __str__() {
            std::ostringstream result;
            for (auto item : *$self) {
                result << " " << item->str() << ", " << std::endl;
            }
            return result.str();
        }
    }
}  // namespace geometry


namespace interp {
    %extend LinearInterpolation1d {
        LinearInterpolation1d(const arma::vec& x, const arma::vec& y, double fill=0.0) {
            return new interp::LinearInterpolation1d(
                std::make_shared<const arma::vec>(x), 
                std::make_shared<const arma::vec>(y), 
                fill);
        }
    }

    %extend LinearInterpolation2d {
        LinearInterpolation2d(const arma::vec& x, const arma::vec& y, const arma::mat& values, double fill=0.0) {
            return new interp::LinearInterpolation2d(
                std::make_shared<const arma::vec>(x), 
                std::make_shared<const arma::vec>(y), 
                std::make_shared<const arma::mat>(values), 
                fill);
        }
    }
}  // namespace interp

namespace oplc {

    %extend Diffraction {
        %ignore c(uint32_t) const;
        %ignore k(uint32_t) const;
        %ignore frq(uint32_t) const;
        %ignore value(uint32_t, uint32_t) const;
        %ignore cx(uint32_t) const;
        %ignore cy(uint32_t) const;
        %ignore kx(uint32_t) const;
        %ignore ky(uint32_t) const;

        %rename(_get_values) values;
        %rename(_get_cxy) cxy;
        
        %rename(_get_cx) cx;
        %rename(_get_cy) cy;

        %rename(_get_frqx) frqx;
        %rename(_get_frqy) frqy;
        
        %rename(_get_kx) kx;
        %rename(_get_ky) ky;
        
        %pythoncode %{
            values = property(_get_values)
            cxy = property(_get_cxy)

            cx = property(_get_cx)
            cy = property(_get_cy)
            
            frqx = property(_get_frqx)
            frqy = property(_get_frqy)
            
            kx = property(_get_kx)
            ky = property(_get_ky)
        %}
    }


    %extend AbstractResistSimulations {    
        %ignore x(uint32_t) const;
        %ignore y(uint32_t) const;
        %ignore z(uint32_t) const;

        %rename(_get_type) type;
        %rename(_get_x) x;
        %rename(_get_y) y;
        %rename(_get_z) z;
        %rename(_has_x) has_x;
        %rename(_has_y) has_y;
        %rename(_has_z) has_z;
        %rename(_axes) axes;

        %pythoncode %{
            type = property(_get_type)
            x = property(_get_x)
            y = property(_get_y)
            z = property(_get_z)
            has_x = property(_has_x)
            has_y = property(_has_y)
            has_z = property(_has_z)
            axes = property(_axes)
        %}
    }


    %extend ResistVolume {
        %ignore value(uint32_t, uint32_t, uint32_t) const;
        %rename(_get_values) values;
        %pythoncode %{
            values = property(_get_values)
        %}
    }


    %extend ResistProfile {
        %rename(_get_polygons) polygons;
        %pythoncode %{
            polygons = property(_get_polygons)
        %}
    }

    %extend Mask {
        %rename(__getitem__) at;
        %rename(__len__) length;
    };


    %extend AbstractWaferLayer {
        %rename(__str__) str;
    };


    %extend ResistWaferLayer {
        static std::shared_ptr<ResistWaferLayer> cast(std::shared_ptr<AbstractWaferLayer> base) {
            return std::dynamic_pointer_cast<ResistWaferLayer>(base);
        }
    }


    %extend WaferStack {
        %rename(__getitem__) operator[];
    };
    
}  // namespace oplc


%ignore _ContourBuilderIterator;
%ignore _ContourEngine;


/* Parse the header file to generate wrappers */
%include "opl_physc.h"
%include "opl_interp.h"
%include "opl_geometry.h"
%include "opl_contours.h"
%include "opl_capi.h"
%include "opl_sim.h"
%include "opl_log.h"
